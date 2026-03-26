# backend/app/api/export.py
"""Account export endpoints: trigger background export and check status."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.models import User
from app.db.session import get_db
from app.infra.redis import get_redis_url

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/export", tags=["export"])

_COOLDOWN_TTL = 86400  # 24 hours in seconds
_STATUS_TTL = 90000  # 25 hours in seconds


def _cooldown_key(user_id: uuid.UUID) -> str:
    return f"export_cooldown:{user_id}"


def _status_key(user_id: uuid.UUID) -> str:
    return f"export_status:{user_id}"


async def _get_redis() -> AsyncIterator[Redis]:
    """Yield a short-lived Redis connection; closed after each request."""
    client = Redis.from_url(get_redis_url(), decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def _enqueue_export(user_id: str) -> None:
    """Enqueue the export_account ARQ task."""
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        await pool.enqueue_job("export_account", user_id=user_id)
    finally:
        await pool.aclose()


class ExportStartResponse(BaseModel):
    message: str


class ExportStatusResponse(BaseModel):
    status: str  # pending | running | done | failed | none
    created_at: str | None = None
    download_url: str | None = None
    expires_at: str | None = None


@router.post("/account", response_model=ExportStartResponse)
@limiter.limit("5/minute")
async def start_account_export(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(_get_redis),
) -> ExportStartResponse:
    """Trigger a full account data export. Rate-limited to once per 24 hours."""
    cooldown_key = _cooldown_key(user.id)
    set_result = await redis.set(cooldown_key, "1", ex=_COOLDOWN_TTL, nx=True)
    if not set_result:
        ttl = await redis.ttl(cooldown_key)
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Export already requested.",
                "retry_after": max(ttl, 0),
            },
        )

    status_data = {
        "status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
    }
    await redis.set(_status_key(user.id), json.dumps(status_data), ex=_STATUS_TTL)
    await _enqueue_export(str(user.id))

    logger.info("account_export_started", user_id=str(user.id))
    return ExportStartResponse(
        message="Export started. You will be notified when ready."
    )


@router.get("/account/status", response_model=ExportStatusResponse)
@limiter.limit("30/minute")
async def get_account_export_status(
    request: Request,
    user: User = Depends(get_current_user),
    redis: Redis = Depends(_get_redis),
) -> ExportStatusResponse:
    """Check the status of the most recent account export."""
    raw = await redis.get(_status_key(user.id))
    if not raw:
        return ExportStatusResponse(status="none")
    data = json.loads(raw)
    return ExportStatusResponse(
        status=data.get("status", "unknown"),
        created_at=data.get("created_at"),
        download_url=data.get("download_url"),
        expires_at=data.get("expires_at"),
    )
