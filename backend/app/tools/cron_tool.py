"""Cron scheduling tools — set, list, and delete recurring agent tasks."""

from __future__ import annotations

import uuid

import structlog
from apscheduler.triggers.cron import CronTrigger
from langchain_core.tools import BaseTool, tool
from sqlalchemy import select

from app.db.models import CronJob
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)


def create_cron_tools(user_id: str) -> tuple[BaseTool, BaseTool, BaseTool]:
    """Return (cron_set, cron_list, cron_delete) tools for the given user."""
    uid = uuid.UUID(user_id)

    @tool
    async def cron_set(schedule: str, task: str) -> str:
        """Schedule a recurring task using a cron expression.

        Args:
            schedule: Cron expression (e.g. "0 9 * * 1-5" = weekdays at 9am,
                      "0 8 * * *" = daily at 8am, "*/30 * * * *" = every 30 min)
            task: Natural language description of what to do when triggered
        """
        try:
            CronTrigger.from_crontab(schedule)
        except ValueError:
            return (
                f"Invalid cron expression: {schedule!r}. "
                "Use standard 5-field cron format, e.g. '0 9 * * 1-5'."
            )
        async with AsyncSessionLocal() as db:
            job = CronJob(user_id=uid, schedule=schedule, task=task)
            db.add(job)
            await db.commit()
            await db.refresh(job)
        from app.scheduler.runner import register_cron_job

        register_cron_job(str(job.id), user_id, schedule, task)
        logger.info("cron_job_created", user_id=user_id, job_id=str(job.id))
        return f"Scheduled: '{task}' with schedule '{schedule}' (id: {job.id})"

    @tool
    async def cron_list() -> str:
        """List all active cron jobs for the current user."""
        async with AsyncSessionLocal() as db:
            rows = await db.scalars(
                select(CronJob)
                .where(CronJob.user_id == uid, CronJob.is_active.is_(True))
                .order_by(CronJob.created_at)
            )
            jobs = rows.all()
        if not jobs:
            return "No active cron jobs."
        lines = ["Active cron jobs:"]
        for j in jobs:
            last = (
                j.last_run_at.strftime("%Y-%m-%d %H:%M") if j.last_run_at else "never"
            )
            lines.append(
                f"- [{j.id}] '{j.task}' | schedule: {j.schedule} | last run: {last}"
            )
        return "\n".join(lines)

    @tool
    async def cron_delete(job_id: str) -> str:
        """Delete (deactivate) a cron job by its ID.

        Args:
            job_id: The UUID of the cron job to delete (from cron_list output)
        """
        try:
            jid = uuid.UUID(job_id)
        except ValueError:
            return f"Invalid job ID: {job_id!r}"
        async with AsyncSessionLocal() as db:
            job = await db.get(CronJob, jid)
            if job is None or job.user_id != uid:
                return f"Cron job {job_id!r} not found."
            job.is_active = False
            await db.commit()
        from app.scheduler.runner import unregister_cron_job

        unregister_cron_job(job_id)
        logger.info("cron_job_deleted", user_id=user_id, job_id=job_id)
        return f"Deleted cron job {job_id}."

    return cron_set, cron_list, cron_delete
