"""Demo mode — runs the full agent pipeline on mock payment data.

Bypasses the Razorpay MCP fetch step and uses local mock payments instead.
Every other step is real: Claude classifies, recovery logic runs (DRY_RUN),
Claude generates the report.

Usage:
    python demo.py
"""
import asyncio
import os

import structlog
from dotenv import load_dotenv

from agent.classifier import PaymentClassifier
from agent.recovery import RecoveryAgent, RecoveryResult
from agent.reporter import RecoveryReporter
from tests.mock_payments import MOCK_PAYMENTS, get_total_value_rupees

load_dotenv()

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger()


async def run_demo() -> None:
    print("\n" + "=" * 60)
    print("RAZORPAY RECOVERY AGENT — DEMO MODE")
    print(f"  {len(MOCK_PAYMENTS)} mock failed payments | Total: RS.{get_total_value_rupees():,.0f}")
    print("=" * 60 + "\n")

    # STEP 1: CLASSIFY
    print("STEP 1/3  Classifying failures with Claude Sonnet 4...\n")
    classifier = PaymentClassifier()
    classified = classifier.classify_batch(MOCK_PAYMENTS)

    for c in classified:
        print(f"  {c.payment_id:<20} {c.failure_type.value:<22} "
              f"RS.{c.amount // 100:>7,}  prob={c.recovery_probability:.0%}  "
              f"priority={c.priority_score:,.0f}")
    print()

    # STEP 2: RECOVER (DRY_RUN)
    print("STEP 2/3  Running recovery strategies (DRY_RUN=true)...\n")

    # Use a mock MCP client — recovery strategies log what they WOULD do
    class _MockMCPClient:
        async def call_tool(self, name, args):
            pass

    recovery_agent = RecoveryAgent(_MockMCPClient())  # type: ignore[arg-type]
    results: list[RecoveryResult] = []

    for payment in classified:
        result = await recovery_agent.recover(payment)
        results.append(result)
        status = "OK " if result.success else "---"
        print(f"  [{status}] {result.payment_id:<20} {result.action_taken:<30} {result.detail}")

    print()

    # STEP 3: REPORT
    print("STEP 3/3  Generating report with Claude Sonnet 4...\n")
    reporter = RecoveryReporter()
    report = reporter.generate(classified, results)

    print("=" * 60)
    print("RECOVERY REPORT")
    print("=" * 60)
    print(report)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
