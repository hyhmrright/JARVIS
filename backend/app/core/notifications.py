"""Notification helper utilities."""

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

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
    db: AsyncSession | None = None,
) -> uuid.UUID:
    """Create a persistent in-app notification for a user.

    If an existing session 'db' is provided, it will be used.
    Otherwise, a new short-lived session is created.
    """
    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id

    if db:
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
    else:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                notification = Notification(
                    user_id=u_id,
                    type=type,
                    title=title,
                    body=body,
                    action_url=action_url,
                    metadata_json=metadata or {},
                )
                session.add(notification)
                await session.flush()
                notification_id = notification.id

    logger.info(
        "notification_created",
        user_id=str(u_id),
        type=type,
        notification_id=str(notification_id),
    )
    return notification_id
