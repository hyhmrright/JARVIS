import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import CronJob, User
from app.db.session import get_db
from app.scheduler.runner import register_cron_job, unregister_cron_job

router = APIRouter(prefix="/api/cron", tags=["cron"])


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
    data: dict[str, Any],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Create a new proactive monitoring job."""
    job = CronJob(
        user_id=user.id,
        schedule=data["schedule"],
        task=data["task"],
        trigger_type=data.get("trigger_type", "cron"),
        trigger_metadata=data.get("trigger_metadata"),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Register with live scheduler
    if job.is_active:
        register_cron_job(str(job.id), str(user.id), job.schedule, job.task)

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
) -> dict[str, str]:
    """Enable or disable a monitoring job."""
    job = await db.get(CronJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    job.is_active = not job.is_active
    await db.commit()

    if job.is_active:
        register_cron_job(str(job.id), str(user.id), job.schedule, job.task)
    else:
        unregister_cron_job(str(job.id))

    return {"status": "ok", "is_active": str(job.is_active)}
