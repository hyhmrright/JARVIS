"""APScheduler lifecycle management — enqueues jobs to ARQ worker."""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from sqlalchemy import select

from app.core.config import settings
from app.db.models import CronJob
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)
_scheduler: AsyncIOScheduler | None = None
_arq_pool: ArqRedis | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def _execute_cron_job(job_id: str) -> None:
    """APScheduler callback: enqueue the job for ARQ worker execution."""
    global _arq_pool
    if _arq_pool is None:
        logger.error("arq_pool_not_initialized", job_id=job_id)
        return
    run_group_id = str(uuid.uuid4())
    await _arq_pool.enqueue_job(
        "execute_cron_job",
        job_id=job_id,
        run_group_id=run_group_id,
    )
    logger.info("cron_job_enqueued", job_id=job_id, run_group_id=run_group_id)


def register_cron_job(job_id: str, schedule: str) -> datetime | None:
    """Register a single cron job with the scheduler. Returns next run time."""
    scheduler = get_scheduler()
    job_key = f"cron_{job_id}"
    if scheduler.get_job(job_key):
        scheduler.remove_job(job_key)
    apscheduler_job = scheduler.add_job(
        _execute_cron_job,
        trigger=CronTrigger.from_crontab(schedule),
        id=job_key,
        kwargs={"job_id": job_id},
        misfire_grace_time=60,
        coalesce=True,
    )
    return apscheduler_job.next_run_time


def unregister_cron_job(job_id: str) -> None:
    """Remove a cron job from the scheduler (no-op if not found)."""
    scheduler = get_scheduler()
    job_key = f"cron_{job_id}"
    if scheduler.get_job(job_key):
        scheduler.remove_job(job_key)


async def _load_cron_jobs() -> None:
    """Load all active CronJob records from DB and register them with APScheduler."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CronJob).where(CronJob.is_active.is_(True)))
        jobs = result.scalars().all()
    for job in jobs:
        register_cron_job(str(job.id), job.schedule)
    logger.info("cron_jobs_loaded", count=len(jobs))


async def start_scheduler() -> None:
    global _arq_pool
    _arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await _load_cron_jobs()
    get_scheduler().start()
    logger.info("scheduler_started")


async def stop_scheduler() -> None:
    global _arq_pool
    get_scheduler().shutdown(wait=False)
    if _arq_pool:
        await _arq_pool.aclose()
        _arq_pool = None
    logger.info("scheduler_stopped")
