"""Webhook management — create, list, and trigger agent tasks from external events."""

from __future__ import annotations

import hmac
import json
import secrets
import uuid
from datetime import UTC, datetime

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.limiter import limiter
from app.db.models import User, Webhook, WebhookDelivery

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    task_template: str = Field(
        min_length=1,
        max_length=2000,
        description="Task description with optional {payload} placeholder",
    )


class WebhookOut(BaseModel):
    id: uuid.UUID
    name: str
    task_template: str
    secret_token: str
    trigger_count: int
    is_active: bool
    last_triggered_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("", status_code=201, response_model=WebhookOut)
async def create_webhook(
    body: WebhookCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebhookOut:
    """Create a new webhook that external services can call to trigger JARVIS."""
    webhook = Webhook(
        user_id=user.id,
        name=body.name,
        task_template=body.task_template,
        secret_token=secrets.token_urlsafe(32),
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)
    logger.info("webhook_created", user_id=str(user.id), webhook_id=str(webhook.id))
    return WebhookOut.model_validate(webhook)


@router.get("", response_model=list[WebhookOut])
async def list_webhooks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookOut]:
    """List all active webhooks for the current user."""
    rows = await db.scalars(
        select(Webhook)
        .where(Webhook.user_id == user.id, Webhook.is_active.is_(True))
        .order_by(Webhook.created_at)
    )
    return [WebhookOut.model_validate(w) for w in rows.all()]


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deactivate (soft-delete) a webhook."""
    webhook = await db.scalar(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.user_id == user.id,
            Webhook.is_active.is_(True),
        )
    )
    if webhook is None:
        raise HTTPException(status_code=404)
    webhook.is_active = False
    await db.commit()
    logger.info("webhook_deleted", user_id=str(user.id), webhook_id=str(webhook_id))


@router.post("/{webhook_id}/trigger", status_code=202)
@limiter.limit("30/minute")
async def trigger_webhook(
    webhook_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger a webhook — called by external services.

    Requires X-Webhook-Secret header matching the webhook's secret_token.
    No authentication token needed (the secret IS the auth).
    """
    webhook = await db.scalar(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.is_active.is_(True))
    )
    if webhook is None:
        raise HTTPException(status_code=404)

    # Constant-time comparison to prevent timing attacks
    provided = request.headers.get("X-Webhook-Secret", "")
    if not hmac.compare_digest(provided, webhook.secret_token):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        payload = await request.json()
    except Exception as exc:
        logger.debug("webhook_json_parse_failed", error=str(exc))
        payload = {}

    payload_str = json.dumps(payload, ensure_ascii=False)[:2000]
    task = webhook.task_template.replace("{payload}", payload_str)

    arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await arq_pool.enqueue_job(
            "deliver_webhook",
            webhook_id=str(webhook_id),
            payload=payload,
        )
    finally:
        await arq_pool.aclose()

    webhook.trigger_count += 1
    webhook.last_triggered_at = datetime.now(UTC)
    await db.commit()

    logger.info(
        "webhook_triggered",
        webhook_id=str(webhook_id),
        user_id=str(webhook.user_id),
        trigger_count=webhook.trigger_count,
    )
    logger.info("webhook_delivery_enqueued", webhook_id=str(webhook_id))

    return {"status": "accepted", "task_preview": task[:200]}


class WebhookDeliveryOut(BaseModel):
    id: uuid.UUID
    webhook_id: uuid.UUID
    triggered_at: datetime
    status: str
    response_code: int | None
    response_body: str | None
    attempt: int
    next_retry_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("/{webhook_id}/deliveries", response_model=list[WebhookDeliveryOut])
async def list_webhook_deliveries(
    webhook_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookDeliveryOut]:
    """Return the last 20 delivery records for a webhook owned by the current user."""
    webhook = await db.scalar(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.user_id == user.id,
        )
    )
    if webhook is None:
        raise HTTPException(status_code=404)

    rows = await db.scalars(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.triggered_at.desc())
        .limit(20)
    )
    return [WebhookDeliveryOut.model_validate(r) for r in rows.all()]
