"""Payment failure classification using Claude Sonnet 4.

Claude reasons about each failure type rather than brittle rule-based matching.
This handles edge cases that rules miss — a new error code from a bank outage
is obvious to Claude even if it's never been seen before.
"""
import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

import anthropic
import structlog

logger = structlog.get_logger()


class FailureType(str, Enum):
    BANK_TECHNICAL = "BANK_TECHNICAL"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    CARD_EXPIRED = "CARD_EXPIRED"
    UPI_TIMEOUT = "UPI_TIMEOUT"
    EVENING_PEAK = "EVENING_PEAK"
    UNKNOWN = "UNKNOWN"


@dataclass
class ClassifiedPayment:
    """A payment failure with its classification and recovery metadata.

    priority_score = (amount_rupees × recovery_probability) — used to sort
    the batch so the agent works highest-value recoverable payments first.
    """
    payment_id: str
    amount: int          # paise
    failure_type: FailureType
    recovery_strategy: str
    recovery_probability: float   # 0.0–1.0
    priority_score: float         # (amount / 100) × recovery_probability
    raw_payment: dict[str, Any]
    reasoning: str = ""


_SYSTEM_PROMPT = """\
You are a payment failure analyst for Indian businesses on Razorpay.

Classify each failed payment into EXACTLY ONE of these failure types:

BANK_TECHNICAL
  Signals: HTTP 502/504, "GATEWAY_ERROR", "bank downtime", "temporary outage"
  Recovery: Auto-retry immediately

INSUFFICIENT_FUNDS
  Signals: "INSUFFICIENT_FUNDS", "BAD_REQUEST_ERROR" with fund-related description
  Recovery: Send payment link reminder after 48 hours (payday cycle)

CARD_EXPIRED
  Signals: "EXPIRED", "INVALID_CARD", card validity errors
  Recovery: Create new payment link immediately

UPI_TIMEOUT
  Signals: method=upi AND "timed out" OR "no confirmation" — amount may have been
  deducted at the bank but not confirmed
  Recovery: Fetch payment status first before any action (safety check)

EVENING_PEAK
  Signals: failure timestamp between 19:00–22:00 IST, gateway congestion
  Recovery: Delay retry until after 22:00 IST

Respond with ONLY valid JSON — no markdown, no explanation:
{
  "failure_type": "<one of the 5 types above>",
  "recovery_strategy": "<one sentence: what to do>",
  "recovery_probability": <float 0.0-1.0>,
  "reasoning": "<one sentence: why this classification>"
}"""


class PaymentClassifier:
    """Classifies payment failures using Claude Sonnet 4.

    Uses JSON-in-prompt rather than tool_use — simpler and faster for
    single flat objects where speed matters more than strict schema validation.
    """

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def classify(self, payment: dict[str, Any]) -> ClassifiedPayment:
        """Classify a single payment failure. Makes one Anthropic API call.

        Only the fields Claude needs are sent — not the full payment object.
        Smaller context means faster and cheaper inference.
        """
        payload = {
            "id": payment.get("id"),
            "amount_rupees": payment.get("amount", 0) / 100,
            "method": payment.get("method"),
            "status": payment.get("status"),
            "error_code": payment.get("error_code"),
            "error_description": payment.get("error_description"),
            "error_source": payment.get("error_source"),
            "created_at_unix": payment.get("created_at"),
        }

        response = self._client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=256,
            system=_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Classify this failed payment:\n{json.dumps(payload, indent=2)}",
            }],
        )

        # Strip markdown fences if Claude wraps the JSON accidentally
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()

        result = json.loads(text)

        failure_type = FailureType(result.get("failure_type", "UNKNOWN"))
        prob = float(result.get("recovery_probability", 0.5))
        amount = payment.get("amount", 0)

        logger.info(
            "payment_classified",
            payment_id=payment.get("id"),
            failure_type=failure_type,
            recovery_probability=prob,
            reasoning=result.get("reasoning"),
        )

        return ClassifiedPayment(
            payment_id=payment.get("id", ""),
            amount=amount,
            failure_type=failure_type,
            recovery_strategy=result.get("recovery_strategy", ""),
            recovery_probability=prob,
            priority_score=(amount / 100) * prob,
            raw_payment=payment,
            reasoning=result.get("reasoning", ""),
        )

    def classify_batch(self, payments: list[dict[str, Any]]) -> list[ClassifiedPayment]:
        """Classify and prioritise a batch of failed payments.

        Sorted by priority_score (value × probability) descending so the agent
        works the highest-value, most-recoverable payments first.
        """
        classified = [self.classify(p) for p in payments]
        return sorted(classified, key=lambda c: c.priority_score, reverse=True)
