"""Entry point for Agent 2 — Razorpay Failed Payment Recovery Agent.

Two run modes:
    once     — single recovery cycle (testing + on-demand)
    schedule — hourly autonomous loop via APScheduler (production)

Separating the two modes makes it easy to verify the agent works correctly
before enabling the autonomous scheduled loop.

Usage:
    python main.py            # run once (default)
    python main.py schedule   # run hourly
"""
import asyncio
import os
import sys

import structlog
from dotenv import load_dotenv

logger = structlog.get_logger()


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.PrintLoggerFactory(),
    )


async def run_once() -> None:
    """Run a single recovery cycle and print the report."""
    from agent.core import RecoveryCore
    core = RecoveryCore()
    report = await core.run_cycle()
    print("\n" + "=" * 60)
    print("RECOVERY REPORT")
    print("=" * 60)
    print(report)
    print("=" * 60)


async def run_scheduled() -> None:
    """Run the agent on a recurring schedule (default: every 60 minutes).

    Runs one cycle immediately on startup so you always get a result right
    away rather than waiting for the first interval to elapse.
    """
    from scheduler.runner import recovery_job, start_scheduler

    logger.info("running_initial_cycle_on_startup")
    await recovery_job()

    scheduler = start_scheduler()
    logger.info("agent_running", tip="press Ctrl+C to stop")

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("agent_stopped")


def main() -> None:
    load_dotenv()
    _configure_logging()

    mode = sys.argv[1] if len(sys.argv) > 1 else "once"
    dry_run = os.environ.get("DRY_RUN", "true")

    logger.info("agent_start", mode=mode, dry_run=dry_run)

    if mode == "schedule":
        asyncio.run(run_scheduled())
    else:
        asyncio.run(run_once())


if __name__ == "__main__":
    main()
