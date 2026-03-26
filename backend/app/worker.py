"""ARQ worker: consumes cron job IDs from Redis queue and executes trigger evaluation."""  # noqa: E501

import asyncio
import json
import os
import tempfile
import time
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

import structlog
from arq.connections import RedisSettings
from arq.cron import cron
from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult

from app.core.config import settings
from app.core.metrics import cron_executions_total
from app.core.notifications import create_notification
from app.db.models import (
    Conversation,
    CronJob,
    Document,
    JobExecution,
    Message,
    UserMemory,
    UserSettings,
    Webhook,
    WebhookDeadLetter,
    WebhookDelivery,
)
from app.db.session import AsyncSessionLocal
from app.gateway.agent_runner import run_agent_for_user
from app.infra.minio import get_minio_client
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
                    db=db,
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
                        db=db,
                    )
                    await db.commit()
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


async def deliver_webhook(ctx: dict, *, webhook_id: str, payload: dict) -> None:
    """ARQ task: deliver webhook payload to the JARVIS agent and record delivery."""
    attempt: int = ctx.get("job_try", 1)
    retry_delays = settings.webhook_retry_delays

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
            if final_status == "failed" and attempt < len(retry_delays):
                delay_s = retry_delays[attempt - 1]
                update_vals["next_retry_at"] = datetime.now(tz=UTC) + timedelta(
                    seconds=delay_s
                )
            await db.execute(
                update(WebhookDelivery)
                .where(WebhookDelivery.id == delivery_id)
                .values(**update_vals)
            )

    if final_status == "failed" and attempt < len(retry_delays):
        delay_s = retry_delays[attempt - 1]
        logger.warning(
            "deliver_webhook_will_retry",
            webhook_id=webhook_id,
            attempt=attempt,
            delay_s=delay_s,
        )
        raise RuntimeError(f"Webhook delivery failed (attempt {attempt}), will retry")

    if final_status == "failed":
        try:
            async with AsyncSessionLocal() as dl_db:
                dead_letter = WebhookDeadLetter(
                    webhook_id=uuid.UUID(webhook_id),
                    user_id=uuid.UUID(user_id),
                    payload=payload,
                    last_error=str(response_body or ""),
                    attempts=attempt,
                )
                dl_db.add(dead_letter)
                await dl_db.commit()
            await create_notification(
                user_id=user_id,
                type="webhook_failed",
                title="Webhook Delivery Failed",
                body=f"Failed to process incoming webhook after {attempt} attempts.",
                action_url="/proactive",
            )
        except Exception:
            logger.warning(
                "deliver_webhook_dead_letter_failed",
                webhook_id=webhook_id,
                exc_info=True,
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


async def cleanup_old_deliveries(ctx: dict) -> None:
    """ARQ periodic task: delete webhook_deliveries older than retention window."""
    retention = settings.webhook_delivery_retention_days
    cutoff = datetime.now(tz=UTC) - timedelta(days=retention)
    async with AsyncSessionLocal() as db:
        result: CursorResult = await db.execute(  # type: ignore[assignment]
            delete(WebhookDelivery).where(WebhookDelivery.triggered_at < cutoff)
        )
        await db.commit()
    logger.info(
        "webhook_deliveries_cleanup",
        deleted=result.rowcount,
        retention_days=retention,
    )


_EXPORT_HOURS = 25
_EXPORT_STATUS_TTL = _EXPORT_HOURS * 3600
_CLEANUP_ZSET_KEY = "export_pending_cleanup"


async def export_account(ctx: dict, *, user_id: str) -> None:
    """ARQ task: package all user data into a ZIP, upload to MinIO, notify user."""
    uid = uuid.UUID(user_id)
    redis = ctx["redis"]
    task_id = str(uuid.uuid4())
    logger.info("export_account_started", user_id=user_id, task_id=task_id)

    started_at = datetime.now(UTC).isoformat()

    async def _set_status(status: str, **extra: object) -> None:
        data = {"status": status, "started_at": started_at, **extra}
        await redis.set(
            f"export_status:{user_id}", json.dumps(data), ex=_EXPORT_STATUS_TTL
        )

    await _set_status("running")

    try:
        async with AsyncSessionLocal() as db:
            conv_rows = await db.scalars(
                select(Conversation).where(Conversation.user_id == uid)
            )
            conv_files: dict[str, str] = {}

            for conv in conv_rows.all():
                msg_rows = await db.scalars(
                    select(Message)
                    .where(
                        Message.conversation_id == conv.id,
                        Message.role.in_(["human", "ai"]),
                    )
                    .order_by(Message.created_at)
                )
                safe_title = conv.title.replace("/", "_").replace("\\", "_")[:80]
                date_prefix = conv.created_at.strftime("%Y-%m-%d")
                lines: list[str] = [
                    f"# {conv.title}",
                    f"> Created: {conv.created_at.isoformat()}",
                    "",
                ]
                for msg in msg_rows.all():
                    prefix = "**用户**" if msg.role == "human" else "**助手**"
                    ts = msg.created_at.strftime("%Y-%m-%d %H:%M")
                    lines.append(f"{prefix} · {ts}")
                    lines.append(msg.content)
                    lines.append("")
                short_id = str(conv.id)[:8]
                conv_files[
                    f"conversations/{date_prefix}_{safe_title}_{short_id}.md"
                ] = "\n".join(lines)

            doc_rows = await db.scalars(
                select(Document).where(
                    Document.user_id == uid,
                    Document.is_deleted.is_(False),
                )
            )
            docs_data = [
                {
                    "id": str(d.id),
                    "filename": d.filename,
                    "file_type": d.file_type,
                    "file_size_bytes": d.file_size_bytes,
                    "chunk_count": d.chunk_count,
                    "created_at": d.created_at.isoformat(),
                    "source_url": d.source_url,
                }
                for d in doc_rows.all()
            ]

            mem_rows = await db.scalars(
                select(UserMemory).where(UserMemory.user_id == uid)
            )
            memories_data = [
                {
                    "id": str(m.id),
                    "key": m.key,
                    "value": m.value,
                    "category": m.category,
                    "created_at": m.created_at.isoformat(),
                }
                for m in mem_rows.all()
            ]

            user_settings = await db.scalar(
                select(UserSettings).where(UserSettings.user_id == uid)
            )
            settings_data: dict[str, object] = {}
            if user_settings:
                settings_data = {
                    "model_provider": user_settings.model_provider,
                    "model_name": user_settings.model_name,
                    "api_keys": "[REDACTED]",
                    "enabled_tools": user_settings.enabled_tools,
                    "persona_override": user_settings.persona_override,
                }

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = tmp.name

        object_key = f"exports/{user_id}/{task_id}.zip"
        minio_client = get_minio_client()
        try:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, content in conv_files.items():
                    zf.writestr(name, content)
                zf.writestr(
                    "documents.json",
                    json.dumps(docs_data, ensure_ascii=False, indent=2),
                )
                zf.writestr(
                    "memories.json",
                    json.dumps(memories_data, ensure_ascii=False, indent=2),
                )
                zf.writestr(
                    "settings.json",
                    json.dumps(settings_data, ensure_ascii=False, indent=2),
                )
            with open(tmp_path, "rb") as f:
                file_size = f.seek(0, 2)
                f.seek(0)
                await asyncio.to_thread(
                    minio_client.put_object,
                    settings.minio_bucket,
                    object_key,
                    f,
                    file_size,
                )
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        download_url = await asyncio.to_thread(
            minio_client.presigned_get_object,
            settings.minio_bucket,
            object_key,
            expires=timedelta(hours=_EXPORT_HOURS),
        )

        expiry_dt = datetime.now(UTC) + timedelta(hours=_EXPORT_HOURS)
        await redis.zadd(_CLEANUP_ZSET_KEY, {object_key: expiry_dt.timestamp()})
        expires_at = expiry_dt.isoformat()

        await create_notification(
            user_id=uid,
            type="account_export_ready",
            title="Account Export Ready",
            body=f"Your data export is ready. Download within {_EXPORT_HOURS} hours.",
            action_url="/settings",
            metadata={"download_url": download_url, "expires_at": expires_at},
        )

        await _set_status("done", download_url=download_url, expires_at=expires_at)
        logger.info("export_account_done", user_id=user_id, task_id=task_id)

    except Exception:
        logger.exception("export_account_failed", user_id=user_id, task_id=task_id)
        await _set_status("failed")
        try:
            await create_notification(
                user_id=uid,
                type="account_export_failed",
                title="Account Export Failed",
                body="An error occurred during export. Please try again later.",
            )
        except Exception:
            logger.exception("export_failure_notification_failed", user_id=user_id)


async def cleanup_expired_exports(ctx: dict) -> None:
    """Hourly cron: delete expired MinIO export objects tracked in Redis sorted set."""
    redis = ctx["redis"]
    now_ts = datetime.now(UTC).timestamp()

    expired_keys = await redis.zrangebyscore(_CLEANUP_ZSET_KEY, 0, now_ts)
    if not expired_keys:
        return

    minio_client = get_minio_client()
    for raw_key in expired_keys:
        object_key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
        try:
            await asyncio.to_thread(
                minio_client.remove_object,
                settings.minio_bucket,
                object_key,
            )
            await redis.zrem(_CLEANUP_ZSET_KEY, object_key)
            logger.info("export_cleanup_deleted", object_key=object_key)
        except Exception:
            logger.warning(
                "export_cleanup_failed", object_key=object_key, exc_info=True
            )


class WorkerSettings:
    functions = [execute_cron_job, deliver_webhook, export_account]
    cron_jobs = [
        cron(cleanup_old_executions, hour=3, minute=0),  # Daily 03:00 UTC
        cron(cleanup_old_deliveries, hour=3, minute=15),  # Daily 03:15 UTC
        cron(cleanup_expired_exports, minute=0),  # Every hour at :00
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300
    retry_jobs = True
    max_tries = 3
