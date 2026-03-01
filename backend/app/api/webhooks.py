"""Webhook management — create, list, and trigger agent tasks from external events."""

from __future__ import annotations

import asyncio
import hmac
import json
import secrets
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import User, Webhook

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Strong references to background tasks so they aren't GC'd before completion.
_background_tasks: set[asyncio.Task] = set()


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
    except Exception:
        payload = {}

    payload_str = json.dumps(payload, ensure_ascii=False)[:2000]
    task = webhook.task_template.replace("{payload}", payload_str)

    webhook.trigger_count += 1
    webhook.last_triggered_at = datetime.now(UTC)
    await db.commit()

    logger.info(
        "webhook_triggered",
        webhook_id=str(webhook_id),
        user_id=str(webhook.user_id),
        trigger_count=webhook.trigger_count,
    )

    from app.gateway.agent_runner import run_agent_for_user

    bg = asyncio.create_task(run_agent_for_user(str(webhook.user_id), task))
    _background_tasks.add(bg)
    bg.add_done_callback(_background_tasks.discard)
    logger.info("webhook_task_queued", task_preview=task[:200])

    return {"status": "accepted", "task_preview": task[:200]}
