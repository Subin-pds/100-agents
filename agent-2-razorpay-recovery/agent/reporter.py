"""Plain English recovery report generation using Claude Sonnet 4.

Takes a structured summary of the recovery cycle and asks Claude to write
a business-readable report. Inverse of the classifier — structured → natural language.
"""
import os
from typing import Any

import anthropic
import structlog

from agent.classifier import ClassifiedPayment
from agent.recovery import RecoveryResult

logger = structlog.get_logger()

_REPORT_SYSTEM = """\
You are a payment recovery analyst. Write a concise plain English report (under 200 words)
summarising one recovery cycle for an Indian business on Razorpay.

Structure:
1. Total failed payments scanned and their combined value in Rs.
2. How many recovered and total value recovered (show % of total)
3. Breakdown by failure type (counts + values)
4. Pending actions (links to send, retries scheduled)
5. Unrecoverable — needs manual review

Rules:
- Always prefix amounts with Rs. and divide paise by 100
- If DRY RUN is true, start with: "[DRY RUN MODE — no real actions taken]"
- Tone: professional, direct, numbers-first. No jargon.
- No markdown headers, no bullet symbols — plain paragraphs only"""


class RecoveryReporter:
    """Generates plain English reports for each recovery cycle."""

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def generate(
        self,
        classified: list[ClassifiedPayment],
        results: list[RecoveryResult],
    ) -> str:
        """Generate a plain English summary of the recovery cycle."""
        dry_run = any(r.dry_run for r in results)
        total_value = sum(c.amount for c in classified)

        recovered_ids = {r.payment_id for r in results if r.success and not r.dry_run}
        recovered_value = sum(c.amount for c in classified if c.payment_id in recovered_ids)

        by_type: dict[str, dict[str, Any]] = {}
        for c in classified:
            ft = c.failure_type.value
            if ft not in by_type:
                by_type[ft] = {"count": 0, "value_rupees": 0}
            by_type[ft]["count"] += 1
            by_type[ft]["value_rupees"] += c.amount // 100

        summary = {
            "dry_run": dry_run,
            "total_payments": len(classified),
            "total_value_rupees": total_value // 100,
            "recovered_count": len(recovered_ids),
            "recovered_value_rupees": recovered_value // 100,
            "recovery_rate_pct": round(
                (recovered_value / total_value * 100) if total_value else 0, 1
            ),
            "by_failure_type": by_type,
            "actions": [
                {"payment_id": r.payment_id, "action": r.action_taken, "detail": r.detail}
                for r in results
            ],
        }

        response = self._client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=512,
            system=_REPORT_SYSTEM,
            messages=[{
                "role": "user",
                "content": f"Generate a recovery report from this data:\n{summary}",
            }],
        )

        report = response.content[0].text.strip()
        logger.info("report_generated", chars=len(report), dry_run=dry_run)
        return report
