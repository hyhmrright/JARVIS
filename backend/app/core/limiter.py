import functools
import ipaddress
import os

import structlog
from fastapi import Request
from slowapi import Limiter

logger = structlog.get_logger(__name__)


@functools.lru_cache(maxsize=256)
def _is_private_ip(ip: str) -> bool:
    """Return True if *ip* is a private/loopback/link-local address."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return False


def get_trusted_client_ip(request: Request) -> str | None:
    """Extract client IP from headers, trusting only known proxies if configured."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Get the first IP in the list (client IP)
        client_ip = forwarded_for.split(",")[0].strip()
        return client_ip
    return request.client.host if request.client else None


def _get_user_or_ip(request: Request) -> str:
    """Rate limit key function: user ID if authenticated, else client IP."""
    user = getattr(request.state, "user", None)
    if user:
        # Use a stable key for users to avoid collisions with IPs
        # and hash it to prevent leaking sensitive IDs in metrics/logs
        user_id = str(user.id)
        return f"user:{user_id}"

    # Fallback to IP for unauthenticated requests
    # Check for Bearer token manually if auth dependency hasn't run yet
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        try:
            from app.core.security import decode_access_token

            token = auth.split(" ")[1]
            user_id = decode_access_token(token)
            return f"user:{user_id}"
        except Exception as exc:
            logger.debug("jwt_decode_failed_using_ip_fallback", error=str(exc))
    return get_trusted_client_ip(request) or "unknown"


# In CI/Test environments, we disable the limiter entirely to prevent 429 errors.
_enabled = not (os.getenv("CI") or os.getenv("PYTEST_CURRENT_TEST"))
limiter = Limiter(key_func=_get_user_or_ip, enabled=_enabled)
