"""Notification helper utilities."""

import uuid
from typing import Any

import structlog

from app.db.models import Notification
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)


async def create_notification(
    user_id: uuid.UUID | str,
    type: str,
    title: str,
    body: str,
    *,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Create a persistent in-app notification for a user."""
    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id

    async with AsyncSessionLocal() as db:
        async with db.begin():
            notification = Notification(
                user_id=u_id,
                type=type,
                title=title,
                body=body,
                action_url=action_url,
                metadata_json=metadata or {},
            )
            db.add(notification)
            await db.flush()
            notification_id = notification.id

    logger.info(
        "notification_created",
        user_id=str(u_id),
        type=type,
        notification_id=str(notification_id),
    )
    return notification_id
