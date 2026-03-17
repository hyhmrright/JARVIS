import functools
import hashlib
import ipaddress

import structlog
from fastapi import Request
from slowapi import Limiter


@functools.lru_cache(maxsize=256)
def _is_private_ip(ip: str) -> bool:
    """Return True if *ip* is a private, loopback, or link-local address."""
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def get_trusted_client_ip(request: Request) -> str | None:
    """Return the real client IP, trusting proxy headers only for private-IP peers.

    When deployed behind Traefik in Docker, the TCP peer is a private
    network address.  In that case X-Real-IP (set by Traefik) is authoritative.
    When a client connects directly from a public IP, proxy headers are ignored
    to prevent audit-log IP spoofing.

    Note: CGNAT addresses (100.64.0.0/10) are NOT treated as private by Python's
    ipaddress.is_private, so carrier-grade NAT peers will not have their proxy
    headers trusted. This is intentional — CGNAT peers are not internal proxies.
    """
    direct_ip = request.client.host if request.client else None
    if direct_ip and _is_private_ip(direct_ip):
        fwd = request.headers.get("x-forwarded-for")
        proxy_ip = request.headers.get("x-real-ip") or (
            fwd.split(",")[0].strip() if fwd else None
        )
        if proxy_ip:
            return proxy_ip
    return direct_ip


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
    return get_trusted_client_ip(request) or "unknown"


limiter = Limiter(key_func=_get_user_or_ip)
