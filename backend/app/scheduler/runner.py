"""APScheduler lifecycle management — enqueues jobs to ARQ worker."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
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


def parse_trigger(schedule_str: str, start_date: datetime | None = None) -> BaseTrigger:
    """将调度字符串解析为 APScheduler 触发器。

    支持：
    - @every 30s (IntervalTrigger)
    - @every 5m
    - @every 2h
    - @every 1d
    - 标准 crontab 格式 (CronTrigger)
    """
    if schedule_str.startswith("@every "):
        match = re.match(r"@every (\d+)([smhd])", schedule_str)
        if not match:
            raise ValueError(
                f"Invalid interval format: {schedule_str}. Expected e.g. @every 30s"
            )

        value = int(match.group(1))
        unit = match.group(2)
        mapping = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
        return IntervalTrigger(**{mapping[unit]: value}, start_date=start_date)

    # CronTrigger.from_crontab 返回实例，但不支持传递 start_date
    # 我们可以直接使用 CronTrigger 构造函数，或者在创建后修改
    trigger = CronTrigger.from_crontab(schedule_str)
    if start_date:
        trigger.start_date = start_date
    return trigger


def register_cron_job(
    job_id: str, schedule: str, start_date: datetime | None = None
) -> datetime | None:
    """在调度器中注册单个任务。返回下次运行时间。"""
    scheduler = get_scheduler()
    job_key = f"cron_{job_id}"
    if scheduler.get_job(job_key):
        scheduler.remove_job(job_key)

    try:
        trigger = parse_trigger(schedule, start_date=start_date)
    except Exception as exc:
        logger.error(
            "trigger_parsing_failed",
            job_id=job_id,
            schedule=schedule,
            error=str(exc),
        )
        return None

    apscheduler_job = scheduler.add_job(
        _execute_cron_job,
        trigger=trigger,
        id=job_key,
        kwargs={"job_id": job_id},
        misfire_grace_time=60,
        coalesce=True,
    )
    return getattr(apscheduler_job, "next_run_time", None)


def unregister_cron_job(job_id: str) -> None:
    """从调度器中移除任务。"""
    scheduler = get_scheduler()
    job_key = f"cron_{job_id}"
    if scheduler.get_job(job_key):
        scheduler.remove_job(job_key)


async def _load_cron_jobs() -> None:
    """从数据库加载所有激活的任务并注册到 APScheduler。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CronJob).where(CronJob.is_active.is_(True)))
        jobs = result.scalars().all()
    for job in jobs:
        # 注意：这里暂不传递 start_date，因为数据库中尚未持久化该字段或逻辑
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
