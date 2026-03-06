from dataclasses import dataclass
from datetime import UTC

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import DEFAULT_ENABLED_TOOLS
from app.core.security import decode_access_token, resolve_api_keys
from app.db.models import User, UserRole, UserSettings
from app.db.session import get_db

security = HTTPBearer()


@dataclass(frozen=True, slots=True)
class ResolvedLLMConfig:
    """Immutable container for resolved LLM provider settings."""

    provider: str
    model_name: str
    api_key: str
    api_keys: list[str]
    enabled_tools: list[str] | None
    persona_override: str | None
    raw_keys: dict[str, str]


async def _resolve_user(
    token: str, db: AsyncSession, request: Request | None = None
) -> User:
    """Authenticate by JWT or PAT token and return the active user.

    PAT tokens start with ``jv_``. Scope is stored in
    ``request.state.api_key_scope`` for optional downstream enforcement.
    JWT tokens always get scope ``full``.
    """
    if token.startswith("jv_"):
        return await _resolve_pat(token, db, request)
    return await _resolve_jwt(token, db, request)


async def _resolve_jwt(
    token: str, db: AsyncSession, request: Request | None = None
) -> User:
    try:
        user_id = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc
    user = await db.scalar(
        select(User).where(User.id == user_id, User.is_active == True)  # noqa: E712
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if request is not None:
        request.state.api_key_scope = "full"
    return user


async def _resolve_pat(
    token: str, db: AsyncSession, request: Request | None = None
) -> User:
    import hashlib
    from datetime import datetime

    from app.db.models import ApiKey

    key_hash = hashlib.sha256(token.encode()).hexdigest()
    api_key = await db.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash))
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )
    if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired"
        )
    user = await db.scalar(
        select(User).where(User.id == api_key.user_id, User.is_active == True)  # noqa: E712
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    # Update last_used_at in an isolated session to avoid committing the
    # shared request session from within the auth dependency.
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as _session:
        async with _session.begin():
            result = await _session.scalar(
                select(ApiKey).where(ApiKey.id == api_key.id)
            )
            if result is not None:
                result.last_used_at = datetime.now(UTC)
    if request is not None:
        request.state.api_key_scope = api_key.scope
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
) -> User:
    return await _resolve_user(credentials.credentials, db, request)


async def get_current_user_query_token(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
) -> User:
    """Authenticate via ?token= query param (for SSE endpoints where headers
    aren't supported)."""
    return await _resolve_user(token, db, request)


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """Ensure the current user has administrative privileges."""
    if user.role not in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def get_llm_config(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResolvedLLMConfig:
    """Load user LLM settings and resolve a valid API key.

    Raises ``HTTPException(400)`` when no API key can be found for the
    configured provider (neither user-stored nor server-level).
    """
    settings = await db.scalar(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )

    provider = settings.model_provider if settings else "deepseek"
    model_name = settings.model_name if settings else "deepseek-chat"
    raw_keys = settings.api_keys if settings else {}

    api_keys = resolve_api_keys(provider, raw_keys)
    if not api_keys:
        raise HTTPException(
            status_code=400,
            detail=f"No API key configured for provider '{provider}'. "
            "Set it in Settings or ask the admin to configure a server-level key.",
        )

    return ResolvedLLMConfig(
        provider=provider,
        model_name=model_name,
        api_key=api_keys[0],
        api_keys=api_keys,
        enabled_tools=(
            settings.enabled_tools
            if settings and settings.enabled_tools is not None
            else DEFAULT_ENABLED_TOOLS
        ),
        persona_override=settings.persona_override if settings else None,
        raw_keys=raw_keys,
    )
