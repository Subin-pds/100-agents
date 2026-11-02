"""Main agent loop — orchestrates one full payment recovery cycle.

The 5-step structure:
    DETECT → CLASSIFY → PRIORITISE → RECOVER → REPORT

Each step has a single responsibility, logs its own outcomes, and can be
tested or replaced independently without touching the others.
"""
import os

import structlog

from agent.classifier import PaymentClassifier
from agent.recovery import RecoveryAgent, RecoveryResult
from agent.reporter import RecoveryReporter
from razorpay_mcp.client import get_client
from razorpay_mcp.tools import fetch_failed_payments

logger = structlog.get_logger()


class RecoveryCore:
    """Orchestrates one full payment recovery cycle.

    Owns the loop structure — classifier, recovery agent, and reporter are
    each independent components. Swap the classifier for a rules engine or
    replace the reporter with a Slack integration without touching this class.
    """

    def __init__(self) -> None:
        self._lookback_hours = int(os.environ.get("RECOVERY_LOOKBACK_HOURS", "24"))
        self._classifier = PaymentClassifier()
        self._reporter = RecoveryReporter()

    async def run_cycle(self) -> str:
        """Run one full recovery cycle. Returns the plain English report.

        All MCP tool calls are async and I/O bound — awaiting them lets the
        event loop stay responsive. Blocking here would cause APScheduler to
        miss its interval windows.
        """
        logger.info("recovery_cycle_start", lookback_hours=self._lookback_hours)

        async with get_client() as mcp:

            # ── STEP 1: DETECT ─────────────────────────────────────────
            failed_payments = await fetch_failed_payments(mcp, self._lookback_hours)

            if not failed_payments:
                logger.info("no_failed_payments_found")
                return "No failed payments found in the last 24 hours. Nothing to recover."

            logger.info("failed_payments_detected", count=len(failed_payments))

            # ── STEP 2 + 3: CLASSIFY & PRIORITISE ─────────────────────
            # Claude classifies each failure type, then sorted by value × probability
            classified = self._classifier.classify_batch(failed_payments)
            logger.info(
                "payments_classified_and_prioritised",
                count=len(classified),
                top_priority=classified[0].payment_id if classified else None,
            )

            # ── STEP 4: RECOVER ────────────────────────────────────────
            # Work payments in priority order — highest value recoverable first
            recovery_agent = RecoveryAgent(mcp)
            results: list[RecoveryResult] = []

            for payment in classified:
                result = await recovery_agent.recover(payment)
                results.append(result)
                logger.info(
                    "recovery_action_complete",
                    payment_id=result.payment_id,
                    failure_type=result.failure_type,
                    action=result.action_taken,
                    success=result.success,
                    dry_run=result.dry_run,
                )

            # ── STEP 5: REPORT ─────────────────────────────────────────
            report = self._reporter.generate(classified, results)
            logger.info("recovery_cycle_complete", payments_processed=len(classified))

            return report
