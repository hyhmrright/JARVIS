"""Pairing code system for linking messaging platform users to JARVIS accounts.

Flow:
  1. Unknown sender sends a message → bot replies with a prompt to enter a code.
  2. User generates a 6-digit pairing code in the JARVIS web UI.
  3. User sends the code via the messaging platform.
  4. PairingManager validates the code, the router links the sender to the user.
  5. Subsequent messages route to that user's agent session normally.
"""

import secrets

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)

PAIRING_CODE_TTL = 900  # 15 minutes
PAIRING_PREFIX = "gateway:pairing:"


def _pairing_key(code: str) -> str:
    return f"{PAIRING_PREFIX}{code}"


PAIRING_PROMPT = (
    "Welcome! To connect your messaging account to JARVIS, please generate a "
    "pairing code in the JARVIS web UI and send it here."
)
PAIRING_SUCCESS = "Account linked successfully! You can now chat with JARVIS."
PAIRING_INVALID = (
    "That code is invalid or has expired. "
    "Please generate a new one in the JARVIS web UI."
)


class PairingManager:
    """Manages pairing codes for linking messaging accounts to JARVIS users."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def generate_code(self, user_id: str) -> str:
        """Generate a 6-digit pairing code for a user.

        The code is stored in Redis with a 15-minute TTL.  Any previously
        generated code for the same user is **not** invalidated — the user
        may have multiple outstanding codes on different devices.
        """
        code = f"{secrets.randbelow(1_000_000):06d}"
        await self._redis.set(_pairing_key(code), user_id, ex=PAIRING_CODE_TTL)
        logger.info("pairing_code_generated", user_id=user_id)
        return code

    async def validate_code(self, code: str) -> str | None:
        """Validate a pairing code and return the associated user_id.

        Uses Redis GETDEL for atomic get-and-delete so the code cannot be
        replayed even under concurrent requests.  Returns ``None`` for
        unknown or expired codes.
        """
        raw = await self._redis.getdel(_pairing_key(code))
        if raw is None:
            logger.warning("pairing_code_invalid", code=code[:2] + "****")
            return None
        user_id: str = raw if isinstance(raw, str) else raw.decode()
        logger.info("pairing_code_validated", user_id=user_id)
        return user_id

    async def revoke_code(self, code: str) -> bool:
        """Revoke a pairing code before it expires.

        Returns ``True`` if the code existed and was deleted, ``False`` if it
        was already absent (expired or never generated).
        """
        deleted: int = await self._redis.delete(_pairing_key(code))
        if deleted:
            logger.info("pairing_code_revoked", code=code[:2] + "****")
        return deleted > 0
