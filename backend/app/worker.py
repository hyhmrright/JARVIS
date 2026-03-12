"""ARQ worker: consumes cron job IDs from Redis queue and executes trigger evaluation."""  # noqa: E501

import time
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from arq.connections import RedisSettings
from arq.cron import cron
from sqlalchemy import delete
from sqlalchemy.engine import CursorResult

from app.core.config import settings
from app.db.models import CronJob, JobExecution
from app.db.session import AsyncSessionLocal
from app.gateway.agent_runner import run_agent_for_user
from app.scheduler.triggers import evaluate_trigger

logger = structlog.get_logger(__name__)


async def execute_cron_job(ctx: dict, *, job_id: str, run_group_id: str) -> None:
    """
    ARQ job function. Evaluates trigger condition and optionally runs the agent.

    ctx["redis"]   — arq Redis connection (used for distributed lock)
    ctx["job_try"] — current attempt number (1-indexed, provided by ARQ)
    """
    lock_key = f"cron_lock:{job_id}"
    redis = ctx["redis"]
    attempt: int = ctx.get("job_try", 1)

    # Acquire distributed lock (NX = only set if not exists)
    acquired = await redis.set(lock_key, 1, nx=True, ex=settings.cron_lock_ttl_seconds)
    if not acquired:
        logger.info("cron_job_lock_contention", job_id=job_id)
        return

    start_ms = time.monotonic()
    status = "error"
    trigger_ctx = None
    agent_result = None
    error_msg = None

    try:
        async with AsyncSessionLocal() as db:
            job: CronJob | None = await db.get(CronJob, uuid.UUID(job_id))
            if job is None or not job.is_active:
                logger.info("cron_job_not_found_or_inactive", job_id=job_id)
                return

            # Evaluate trigger (mutates metadata in-place)
            metadata: dict = job.trigger_metadata or {}
            result = await evaluate_trigger(job.trigger_type, metadata)

            if result.fired:
                status = "fired"
                trigger_ctx = result.trigger_ctx
                agent_result = await run_agent_for_user(
                    user_id=str(job.user_id),
                    task=job.task,
                    trigger_ctx=result.trigger_ctx,
                )
                agent_result = (agent_result or "")[:2000]
            else:
                status = "skipped"

            # Capture duration AFTER agent call so it includes agent execution time
            duration_ms = int((time.monotonic() - start_ms) * 1000)

            # Persist state: update metadata + last_run_at + insert execution record
            job.trigger_metadata = metadata
            job.last_run_at = datetime.now(tz=UTC)

            execution = JobExecution(
                job_id=job.id,
                run_group_id=uuid.UUID(run_group_id),
                status=status,
                trigger_ctx=trigger_ctx,
                agent_result=agent_result,
                duration_ms=duration_ms,
                attempt=attempt,
            )
            db.add(execution)
            await db.commit()

            logger.info(
                "cron_job_executed",
                job_id=job_id,
                status=status,
                duration_ms=duration_ms,
            )

    except Exception as exc:
        duration_ms = int((time.monotonic() - start_ms) * 1000)
        error_msg = str(exc)
        logger.exception("cron_job_execution_failed", job_id=job_id, error=error_msg)

        # Write error record
        try:
            async with AsyncSessionLocal() as db:
                execution = JobExecution(
                    job_id=uuid.UUID(job_id),
                    run_group_id=uuid.UUID(run_group_id),
                    status="error",
                    duration_ms=duration_ms,
                    error_msg=error_msg[:1000],
                    attempt=attempt,
                )
                db.add(execution)
                await db.commit()
        except Exception:
            logger.exception("failed_to_write_error_execution", job_id=job_id)

        raise  # Re-raise so ARQ can retry

    finally:
        await redis.delete(lock_key)


async def cleanup_old_executions(ctx: dict) -> None:
    """ARQ periodic task: delete job_executions older than retention window."""
    cutoff = datetime.now(tz=UTC) - timedelta(
        days=settings.cron_execution_retention_days
    )
    async with AsyncSessionLocal() as db:
        result: CursorResult = await db.execute(  # type: ignore[assignment]
            delete(JobExecution).where(JobExecution.fired_at < cutoff)
        )
        await db.commit()
    logger.info(
        "job_executions_cleanup",
        deleted=result.rowcount,
        retention_days=settings.cron_execution_retention_days,
    )


class WorkerSettings:
    functions = [execute_cron_job]
    cron_jobs = [
        cron(cleanup_old_executions, hour=3, minute=0)  # Daily 03:00 UTC
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300
    retry_jobs = True
    max_tries = 3
