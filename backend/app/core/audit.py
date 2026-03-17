"""Audit log utilities for recording security-relevant user actions."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog

from app.core.limiter import get_trusted_client_ip
from app.db.models import AuditLog
from app.db.session import AsyncSessionLocal

if TYPE_CHECKING:
    from fastapi import Request

logger = structlog.get_logger(__name__)


async def log_action(
    action: str,
    *,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request: Request | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Persist an audit log entry asynchronously.

    Failures are swallowed and logged — audit logging must never break the
    primary request path.
    """
    ip_address: str | None = None
    user_agent: str | None = None
    if request is not None:
        ip_address = get_trusted_client_ip(request)
        raw_ua = request.headers.get("user-agent", "")
        user_agent = raw_ua[:1000] or None

    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                session.add(
                    AuditLog(
                        user_id=user_id,
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        extra=extra,
                    )
                )
    except Exception:
        logger.warning(
            "audit_log_failed",
            action=action,
            user_id=str(user_id) if user_id else None,
            exc_info=True,
        )
