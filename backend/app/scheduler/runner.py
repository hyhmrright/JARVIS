"""APScheduler lifecycle management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = structlog.get_logger(__name__)
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def _execute_cron_job(job_id: str, user_id: str, task: str) -> None:
    """Callback invoked by APScheduler when a cron job fires."""

    from app.db.models import CronJob
    from app.db.session import AsyncSessionLocal
    from app.gateway.agent_runner import run_agent_for_user
    from app.scheduler.triggers import evaluate_trigger

    logger.info("cron_job_firing", job_id=job_id, user_id=user_id)

    async with AsyncSessionLocal() as db:
        job = await db.get(CronJob, uuid.UUID(job_id))
        if not job or not job.is_active:
            logger.info("cron_job_skipped_inactive", job_id=job_id)
            return

        # NEW: Evaluate proactive trigger condition (e.g. web watcher)
        metadata = dict(job.trigger_metadata or {})
        if not await evaluate_trigger(job.trigger_type, metadata):
            logger.info("proactive_trigger_skipped_no_change", job_id=job_id)
            return

        # Update metadata (e.g. last_hash) and execution time
        job.trigger_metadata = metadata
        job.last_run_at = datetime.now(UTC)
        await db.commit()

    await run_agent_for_user(user_id, task)


def register_cron_job(job_id: str, user_id: str, schedule: str, task: str) -> None:
    """Register a single cron job with the scheduler (idempotent)."""
    scheduler = get_scheduler()
    try:
        trigger = CronTrigger.from_crontab(schedule)
        scheduler.add_job(
            _execute_cron_job,
            trigger=trigger,
            args=[job_id, user_id, task],
            id=job_id,
            replace_existing=True,
        )
        logger.info("cron_job_registered", job_id=job_id)
    except Exception:
        logger.warning("cron_job_register_failed", job_id=job_id, exc_info=True)


def unregister_cron_job(job_id: str) -> None:
    """Remove a cron job from the scheduler (no-op if not found)."""
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(job_id)
        logger.info("cron_job_unregistered", job_id=job_id)
    except Exception:
        pass  # Job may not be in scheduler (e.g. after server restart)


async def _load_cron_jobs() -> None:
    """Load all active CronJob records from DB and register them with APScheduler."""
    from sqlalchemy import select

    from app.db.models import CronJob
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rows = await db.scalars(select(CronJob).where(CronJob.is_active.is_(True)))
        jobs = rows.all()

    for job in jobs:
        register_cron_job(
            job_id=str(job.id),
            user_id=str(job.user_id),
            schedule=job.schedule,
            task=job.task,
        )
    logger.info("cron_jobs_loaded", count=len(jobs))


async def start_scheduler() -> None:
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("scheduler_started")
    await _load_cron_jobs()


async def stop_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
