"""CronJob business logic — extracted from api/cron.py.

Owns: validation, quota enforcement, metadata encryption, scheduler registration.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import HTTPException
from sqlalchemy import func as sql_func
from sqlalchemy import select

from app.core.config import settings
from app.core.security import fernet_encrypt
from app.db.models import CronJob
from app.scheduler.runner import register_cron_job, unregister_cron_job
from app.scheduler.trigger_schemas import validate_trigger_metadata

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class CronService:
    """Domain service for CronJob lifecycle operations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def check_quota(self, user_id: uuid.UUID) -> None:
        """Raise 429 if the user has reached the active job limit."""
        active_count = await self._db.scalar(
            select(sql_func.count()).where(
                CronJob.user_id == user_id,
                CronJob.is_active.is_(True),
            )
        )
        if (active_count or 0) >= settings.max_cron_jobs_per_user:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Job quota exceeded "
                    f"(max {settings.max_cron_jobs_per_user} active jobs)"
                ),
            )

    def prepare_trigger_metadata(
        self,
        trigger_type: str,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Encrypt sensitive fields in trigger metadata (e.g. email passwords)."""
        if metadata is None:
            return None
        result = dict(metadata)
        if trigger_type == "email" and "imap_password" in result:
            result["imap_password"] = fernet_encrypt(str(result["imap_password"]))
        return result

    async def create_job(
        self,
        *,
        user_id: uuid.UUID,
        schedule: str,
        task: str,
        trigger_type: str,
        trigger_metadata: dict[str, Any] | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> CronJob:
        """Validate, enforce quota, persist, and register a new CronJob."""
        try:
            CronJob.validate_trigger_type(trigger_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            validate_trigger_metadata(trigger_type, trigger_metadata or {})
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid trigger_metadata: {exc}",
            ) from exc

        await self.check_quota(user_id)

        prepared_metadata = self.prepare_trigger_metadata(
            trigger_type, trigger_metadata
        )

        job = CronJob.create(
            user_id=user_id,
            schedule=schedule,
            task=task,
            trigger_type=trigger_type,
            workspace_id=workspace_id,
            trigger_metadata=prepared_metadata,
        )
        self._db.add(job)

        if job.is_active:
            next_run_time = register_cron_job(str(job.id), job.schedule)
            if next_run_time:
                job.next_run_at = next_run_time

        await self._db.commit()
        await self._db.refresh(job)
        return job

    async def update_job(
        self,
        job: CronJob,
        *,
        schedule: str | None = None,
        task: str | None = None,
        trigger_metadata: dict[str, Any] | None = None,
    ) -> CronJob:
        """Update mutable fields on an existing job, re-register if active."""
        if trigger_metadata is not None:
            try:
                validate_trigger_metadata(job.trigger_type, trigger_metadata)
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid trigger_metadata: {exc}",
                ) from exc

        if schedule is not None:
            job.schedule = schedule
        if task is not None:
            job.task = task
        if trigger_metadata is not None:
            job.trigger_metadata = self.prepare_trigger_metadata(
                job.trigger_type, trigger_metadata
            )

        if job.is_active:
            unregister_cron_job(str(job.id))
            next_run_time = register_cron_job(str(job.id), job.schedule)
            if next_run_time:
                job.next_run_at = next_run_time

        await self._db.commit()
        return job

    async def delete_job(self, job: CronJob) -> None:
        """Unregister and delete a job."""
        unregister_cron_job(str(job.id))
        await self._db.delete(job)
        await self._db.commit()

    async def toggle_job(self, job: CronJob) -> CronJob:
        """Toggle active/inactive and update scheduler registration."""
        job.toggle()

        if job.is_active:
            next_run_time = register_cron_job(str(job.id), job.schedule)
            if next_run_time:
                job.next_run_at = next_run_time
        else:
            unregister_cron_job(str(job.id))
            job.next_run_at = None

        await self._db.commit()
        return job
