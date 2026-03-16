import hashlib

import structlog
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = structlog.get_logger(__name__)


def _get_user_or_ip(request: Request) -> str:
    """Per-user key for authenticated requests; fall back to IP for anonymous.

    For JWT tokens: decodes the Bearer token to obtain the user ID.
    For PAT tokens (jv_*): uses a hash of the token itself as the key,
    ensuring per-key (and thus per-user) rate limiting without a DB lookup.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        if token.startswith("jv_"):
            # PAT: use hash of token as stable per-key identifier
            token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
            return f"pat:{token_hash}"
        try:
            from app.core.security import decode_access_token

            user_id = decode_access_token(token)
            return f"user:{user_id}"
        except Exception as exc:
            logger.debug("jwt_decode_failed_using_ip_fallback", error=str(exc))
    return get_remote_address(request)


limiter = Limiter(key_func=_get_user_or_ip)
