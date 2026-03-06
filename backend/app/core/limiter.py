from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_user_or_ip(request: Request) -> str:
    """Per-user key for authenticated requests; fall back to IP for anonymous.

    Decodes the Bearer token from the Authorization header to obtain the user
    ID without requiring FastAPI dependency injection (which runs after slowapi).
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from app.core.security import decode_access_token

            user_id = decode_access_token(auth[7:])
            return f"user:{user_id}"
        except Exception:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_get_user_or_ip)
