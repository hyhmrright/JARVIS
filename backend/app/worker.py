"""ARQ worker: consumes cron job IDs from Redis queue and executes trigger evaluation."""  # noqa: E501

import time
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from arq.connections import RedisSettings
from arq.cron import cron
from sqlalchemy import delete, update
from sqlalchemy.engine import CursorResult

from app.core.config import settings
from app.core.metrics import cron_executions_total
from app.core.notifications import create_notification
from app.db.models import CronJob, JobExecution, Webhook, WebhookDelivery
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
                cron_executions_total.labels(status="fired").inc()

                await create_notification(
                    user_id=job.user_id,
                    type="cron_completed",
                    title=f"Automation Fired: {job.task[:30]}...",
                    body="Trigger matched and agent task executed successfully.",
                    action_url="/proactive",
                )

            else:
                status = "skipped"
                cron_executions_total.labels(status="skipped").inc()

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
        cron_executions_total.labels(status="error").inc()

        # 发送失败通知
        try:
            async with AsyncSessionLocal() as db:
                job_obj = await db.get(CronJob, uuid.UUID(job_id))
                if job_obj:
                    await create_notification(
                        user_id=job_obj.user_id,
                        type="cron_failed",
                        title=f"Automation Failed: {job_obj.task[:30]}...",
                        body=f"Error: {error_msg[:100]}",
                        action_url="/proactive",
                    )
        except Exception:
            pass

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


# Delays (seconds) before each retry: attempt 1→2 waits 1s, attempt 2→3 waits 10s
_WEBHOOK_RETRY_DELAYS = [1, 10]


async def deliver_webhook(ctx: dict, *, webhook_id: str, payload: dict) -> None:
    """ARQ task: deliver webhook payload to the JARVIS agent and record delivery."""
    attempt: int = ctx.get("job_try", 1)

    async with AsyncSessionLocal() as db:
        webhook: Webhook | None = await db.get(Webhook, uuid.UUID(webhook_id))
        if webhook is None or not webhook.is_active:
            logger.info("deliver_webhook_skipped_inactive", webhook_id=webhook_id)
            return

        delivery = WebhookDelivery(
            webhook_id=uuid.UUID(webhook_id),
            status="pending",
            attempt=attempt,
        )
        db.add(delivery)
        await db.flush()
        delivery_id = delivery.id

        task_str = webhook.task_template.replace("{payload}", str(payload)[:2000])
        user_id = str(webhook.user_id)
        await db.commit()

    # Run the agent outside DB session
    final_status = "failed"
    response_body: str | None = None

    try:
        agent_result = await run_agent_for_user(user_id=user_id, task=task_str)
        final_status = "success"
        response_body = (agent_result or "")[:4000]
    except Exception as exc:
        response_body = str(exc)[:4000]
        logger.exception(
            "deliver_webhook_agent_failed",
            webhook_id=webhook_id,
            attempt=attempt,
        )

    async with AsyncSessionLocal() as db:
        async with db.begin():
            update_vals: dict = {
                "status": final_status,
                "response_body": response_body,
            }
            if final_status == "failed" and attempt < len(_WEBHOOK_RETRY_DELAYS):
                delay_s = _WEBHOOK_RETRY_DELAYS[attempt - 1]
                update_vals["next_retry_at"] = datetime.now(tz=UTC) + timedelta(
                    seconds=delay_s
                )
            await db.execute(
                update(WebhookDelivery)
                .where(WebhookDelivery.id == delivery_id)
                .values(**update_vals)
            )

    if final_status == "failed" and attempt < len(_WEBHOOK_RETRY_DELAYS):
        delay_s = _WEBHOOK_RETRY_DELAYS[attempt - 1]
        logger.warning(
            "deliver_webhook_will_retry",
            webhook_id=webhook_id,
            attempt=attempt,
            delay_s=delay_s,
        )
        raise RuntimeError(f"Webhook delivery failed (attempt {attempt}), will retry")

    if final_status == "failed":
        await create_notification(
            user_id=user_id,
            type="webhook_failed",
            title="Webhook Delivery Failed",
            body=f"Failed to process incoming webhook after {attempt} attempts.",
            action_url="/proactive",
        )

    logger.info(
        "deliver_webhook_done",
        webhook_id=webhook_id,
        status=final_status,
        attempt=attempt,
    )


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
    functions = [execute_cron_job, deliver_webhook]
    cron_jobs = [
        cron(cleanup_old_executions, hour=3, minute=0)  # Daily 03:00 UTC
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300
    retry_jobs = True
    max_tries = 3
