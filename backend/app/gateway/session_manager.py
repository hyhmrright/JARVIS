import json
from typing import Any

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)

_SESSION_TTL_SECONDS = 86400  # 24 hours


def _session_key(channel: str, sender_id: str) -> str:
    return f"gateway:session:{channel}:{sender_id}"


class SessionManager:
    """Manages user sessions across channels.

    Links (channel, sender_id) to a JARVIS user_id and stores lightweight
    session state in Redis.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get_or_create_session(
        self, sender_id: str, channel: str
    ) -> dict[str, Any]:
        """Return the session dict for (channel, sender_id), creating it if absent."""
        key = _session_key(channel, sender_id)
        raw = await self._redis.get(key)
        if raw is not None:
            session: dict[str, Any] = json.loads(raw)
            logger.debug("session_found", channel=channel, sender_id=sender_id)
            return session

        session = {"sender_id": sender_id, "channel": channel, "user_id": None}
        await self._redis.setex(key, _SESSION_TTL_SECONDS, json.dumps(session))
        logger.info("session_created", channel=channel, sender_id=sender_id)
        return session

    async def link_user(self, sender_id: str, channel: str, user_id: str) -> None:
        """Associate a JARVIS user_id with this channel session."""
        session = await self.get_or_create_session(sender_id, channel)
        session["user_id"] = user_id
        key = _session_key(channel, sender_id)
        await self._redis.setex(key, _SESSION_TTL_SECONDS, json.dumps(session))
        logger.info(
            "session_linked",
            channel=channel,
            sender_id=sender_id,
            user_id=user_id,
        )

    async def delete_session(self, sender_id: str, channel: str) -> None:
        """Remove the session for (channel, sender_id)."""
        key = _session_key(channel, sender_id)
        await self._redis.delete(key)
        logger.info("session_deleted", channel=channel, sender_id=sender_id)
