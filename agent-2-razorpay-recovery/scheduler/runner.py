"""APScheduler hourly job — runs the recovery cycle autonomously.

APScheduler is appropriate for single-process scheduled agents. For production
at scale, graduate to Celery beat, Cloud Scheduler, or Temporal — APScheduler
doesn't survive process restarts.
"""
import asyncio
import os

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from agent.core import RecoveryCore

logger = structlog.get_logger()


async def recovery_job() -> None:
    """One scheduled recovery cycle — called by APScheduler on each interval.

    RecoveryCore is instantiated fresh each run so the cycle is stateless.
    State that must persist across runs (e.g. retry counts) belongs in a
    database, not in-memory on this object.
    """
    logger.info("scheduled_recovery_job_start")
    try:
        core = RecoveryCore()
        report = await core.run_cycle()
        print("\n" + "=" * 60)
        print("RECOVERY REPORT")
        print("=" * 60)
        print(report)
        print("=" * 60 + "\n")
    except Exception as e:
        logger.error("scheduled_job_failed", error=str(e), exc_info=True)


def start_scheduler() -> AsyncIOScheduler:
    """Create and start the APScheduler with the configured interval."""
    interval_minutes = int(os.environ.get("SCHEDULE_INTERVAL_MINUTES", "60"))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        recovery_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="razorpay_recovery",
        name="Razorpay Failed Payment Recovery",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("scheduler_started", interval_minutes=interval_minutes)
    return scheduler
