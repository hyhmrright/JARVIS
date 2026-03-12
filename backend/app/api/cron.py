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

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import fernet_encrypt
from app.db.models import CronJob, JobExecution, User
from app.db.session import get_db
from app.gateway.agent_runner import run_agent_for_user
from app.scheduler.runner import register_cron_job, unregister_cron_job
from app.scheduler.triggers import evaluate_trigger

router = APIRouter(prefix="/api/cron", tags=["cron"])

_VALID_TRIGGER_TYPES = {"cron", "web_watcher", "semantic_watcher", "email"}


class CronJobCreate(BaseModel):
    schedule: str = Field(min_length=1, max_length=100)
    task: str = Field(min_length=1, max_length=4000)
    trigger_type: str = Field(default="cron", max_length=50)
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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all proactive monitoring jobs for the current user."""
    result = await db.scalars(select(CronJob).where(CronJob.user_id == user.id))
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
        }
        for j in jobs
    ]


@router.post("")
async def create_cron_job(
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

    # Encrypt sensitive fields in trigger_metadata before storage
    trigger_metadata = dict(data.trigger_metadata) if data.trigger_metadata else None
    if trigger_metadata and data.trigger_type == "email":
        if "imap_password" in trigger_metadata:
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
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Register with live scheduler
    if job.is_active:
        register_cron_job(str(job.id), job.schedule)

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
        register_cron_job(str(job.id), job.schedule)
    else:
        unregister_cron_job(str(job.id))

    return {"status": "ok", "is_active": job.is_active}


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
