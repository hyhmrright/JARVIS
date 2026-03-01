"""APScheduler lifecycle management."""

from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = structlog.get_logger(__name__)
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def start_scheduler() -> None:
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("scheduler_started")


async def stop_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
