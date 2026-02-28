"""HTTP endpoints for the messaging gateway (pairing code generation)."""

from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.api.deps import get_current_user
from app.db.models import User
from app.gateway.security import PAIRING_CODE_TTL, PairingManager
from app.infra.redis import get_redis_url

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/gateway", tags=["gateway"])


async def _get_redis() -> AsyncIterator[Redis]:
    """Yield a short-lived Redis connection for a single request.

    This factory is intentionally lightweight -- it opens one connection per
    request rather than pooling, which is acceptable for the low-frequency
    pairing endpoint.  The connection is closed after the request completes.
    """
    client = Redis.from_url(get_redis_url(), decode_responses=False)
    try:
        yield client
    finally:
        await client.aclose()


@router.post("/pair")
async def generate_pairing_code(
    user: User = Depends(get_current_user),
    redis: Redis = Depends(_get_redis),
) -> dict[str, str | int]:
    """Generate a pairing code so the user can link a messaging account.

    The code is a zero-padded 6-digit string (e.g. ``"042713"``) that the
    user must send via their messaging platform (Telegram, Discord, etc.)
    within 15 minutes.
    """
    manager = PairingManager(redis)
    code = await manager.generate_code(str(user.id))
    logger.info("pairing_code_endpoint_called", user_id=str(user.id))
    return {"code": code, "expires_in": PAIRING_CODE_TTL}
