import asyncio
import time
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func as sql_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_workspace_member
from app.core.config import settings
from app.core.security import fernet_encrypt
from app.db.models import CronJob, JobExecution, User
from app.db.session import get_db
from app.gateway.agent_runner import run_agent_for_user
from app.scheduler.runner import register_cron_job, unregister_cron_job
from app.scheduler.trigger_schemas import validate_trigger_metadata
from app.scheduler.triggers import evaluate_trigger

router = APIRouter(prefix="/api/cron", tags=["cron"])

_VALID_TRIGGER_TYPES = {"cron", "web_watcher", "semantic_watcher", "email"}


class CronJobCreate(BaseModel):
    schedule: str = Field(min_length=1, max_length=100)
    task: str = Field(min_length=1, max_length=4000)
    trigger_type: str = Field(default="cron", max_length=50)
    trigger_metadata: dict[str, Any] | None = None
    workspace_id: uuid.UUID | None = None


class CronJobUpdate(BaseModel):
    schedule: str | None = Field(default=None, min_length=1, max_length=100)
    task: str | None = Field(default=None, min_length=1, max_length=4000)
    trigger_metadata: dict[str, Any] | None = None


class JobExecutionSchema(BaseModel):
    id: uuid.UUID
    run_group_id: uuid.UUID
    fired_at: datetime
    status: str
    trigger_ctx: dict | None
    agent_result: str | None
    duration_ms: int | None
    error_msg: str | None
    attempt: int

    model_config = {"from_attributes": True}


class TestTriggerResponse(BaseModel):
    triggered: bool
    trigger_ctx: dict | None
    agent_result: str | None
    is_error: bool
    duration_ms: int


@router.get("")
async def list_cron_jobs(
    workspace_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all proactive monitoring jobs for the current user."""
    query = select(CronJob).where(CronJob.user_id == user.id)
    if workspace_id is not None:
        await require_workspace_member(workspace_id, user, db)
        query = query.where(CronJob.workspace_id == workspace_id)
    result = await db.scalars(query)
    jobs = result.all()
    return [
        {
            "id": str(j.id),
            "schedule": j.schedule,
            "task": j.task,
            "trigger_type": j.trigger_type,
            "trigger_metadata": j.trigger_metadata,
            "is_active": j.is_active,
            "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
            "next_run_at": j.next_run_at.isoformat() if j.next_run_at else None,
            "workspace_id": str(j.workspace_id) if j.workspace_id else None,
        }
        for j in jobs
    ]


@router.post("")
async def create_cron_job(  # noqa: C901
    data: CronJobCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Create a new proactive monitoring job."""
    if data.trigger_type not in _VALID_TRIGGER_TYPES:
        valid = sorted(_VALID_TRIGGER_TYPES)
        raise HTTPException(
            status_code=400, detail=f"Invalid trigger_type. Must be one of: {valid}"
        )

    # Quota check
    active_count = await db.scalar(
        select(sql_func.count()).where(
            CronJob.user_id == user.id,
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

    # Validate trigger metadata
    try:
        validate_trigger_metadata(data.trigger_type, data.trigger_metadata or {})
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid trigger_metadata: {exc}",
        ) from exc

    # Encrypt sensitive fields in trigger_metadata before storage
    trigger_metadata = dict(data.trigger_metadata) if data.trigger_metadata else None
    if (
        trigger_metadata
        and data.trigger_type == "email"
        and "imap_password" in trigger_metadata
    ):
        trigger_metadata["imap_password"] = fernet_encrypt(
            str(trigger_metadata["imap_password"])
        )

    job = CronJob(
        user_id=user.id,
        schedule=data.schedule,
        task=data.task,
        trigger_type=data.trigger_type,
        trigger_metadata=trigger_metadata,
    )
    if data.workspace_id is not None:
        await require_workspace_member(data.workspace_id, user, db)
        job.workspace_id = data.workspace_id
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Register with live scheduler
    if job.is_active:
        next_run_time = register_cron_job(str(job.id), job.schedule)
        if next_run_time:
            job.next_run_at = next_run_time
            await db.commit()

    return {"status": "ok", "id": str(job.id)}


@router.delete("/{job_id}")
async def delete_cron_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete a monitoring job."""
    job = await db.get(CronJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    unregister_cron_job(str(job.id))
    await db.delete(job)
    await db.commit()
    return {"status": "ok"}


@router.patch("/{job_id}/toggle")
async def toggle_cron_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Enable or disable a monitoring job."""
    job = await db.get(CronJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    job.is_active = not job.is_active
    await db.commit()

    if job.is_active:
        next_run_time = register_cron_job(str(job.id), job.schedule)
        if next_run_time:
            job.next_run_at = next_run_time
            await db.commit()
    else:
        unregister_cron_job(str(job.id))
        job.next_run_at = None
        await db.commit()

    return {"status": "ok", "is_active": job.is_active}


@router.put("/{job_id}")
async def update_cron_job(
    job_id: uuid.UUID,
    data: CronJobUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update schedule, task, or trigger_metadata of an existing job."""
    job = await db.get(CronJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    if data.trigger_metadata is not None:
        try:
            validate_trigger_metadata(job.trigger_type, data.trigger_metadata)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid trigger_metadata: {exc}",
            ) from exc

    if data.schedule is not None:
        job.schedule = data.schedule
    if data.task is not None:
        job.task = data.task
    if data.trigger_metadata is not None:
        trigger_metadata = dict(data.trigger_metadata)
        if job.trigger_type == "email" and "imap_password" in trigger_metadata:
            trigger_metadata["imap_password"] = fernet_encrypt(
                str(trigger_metadata["imap_password"])
            )
        job.trigger_metadata = trigger_metadata

    await db.commit()

    if job.is_active:
        unregister_cron_job(str(job.id))
        next_run_time = register_cron_job(str(job.id), job.schedule)
        if next_run_time:
            job.next_run_at = next_run_time
            await db.commit()

    return {"status": "ok", "id": str(job.id)}


@router.get("/{job_id}/history", response_model=list[JobExecutionSchema])
async def get_job_history(
    job_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[JobExecutionSchema]:
    """Return execution history for a job, one record per logical run group."""
    job = await db.get(CronJob, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    # Group by run_group_id using CTE: return terminal row (highest attempt) per group
    ranked_cte = (
        select(
            JobExecution,
            sql_func.row_number()
            .over(
                partition_by=JobExecution.run_group_id,
                order_by=JobExecution.attempt.desc(),
            )
            .label("rn"),
        )
        .where(JobExecution.job_id == job_id)
        .cte("ranked_executions")
    )
    result = await db.execute(
        select(JobExecution)
        .join(ranked_cte, JobExecution.id == ranked_cte.c.id)
        .where(ranked_cte.c.rn == 1)
        .order_by(ranked_cte.c.fired_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/{job_id}/test", response_model=TestTriggerResponse)
async def test_trigger(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TestTriggerResponse:
    """Run a trigger evaluation + agent invocation synchronously (max 30s)."""
    job = await db.get(CronJob, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    start = time.monotonic()

    async def _run() -> tuple[bool, dict | None, str | None, bool]:
        metadata = dict(job.trigger_metadata or {})
        result = await evaluate_trigger(job.trigger_type, metadata)
        if not result.fired:
            return False, None, None, False
        agent_result = await run_agent_for_user(
            user_id=str(job.user_id),
            task=job.task,
            trigger_ctx=result.trigger_ctx,
        )
        is_error = (agent_result or "").startswith("[Error")
        return True, result.trigger_ctx, agent_result, is_error

    try:
        triggered, trigger_ctx, agent_result, is_error = await asyncio.wait_for(
            _run(), timeout=30.0
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="Trigger evaluation timed out after 30s"
        ) from exc

    duration_ms = int((time.monotonic() - start) * 1000)
    return TestTriggerResponse(
        triggered=triggered,
        trigger_ctx=trigger_ctx,
        agent_result=agent_result,
        is_error=is_error,
        duration_ms=duration_ms,
    )
