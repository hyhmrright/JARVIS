from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, resolve_api_key
from app.db.models import User, UserSettings
from app.db.session import get_db

security = HTTPBearer()


@dataclass(frozen=True, slots=True)
class ResolvedLLMConfig:
    """Immutable container for resolved LLM provider settings."""

    provider: str
    model_name: str
    api_key: str
    enabled_tools: list[str] | None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        user_id = decode_access_token(credentials.credentials)
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
    return user


async def get_llm_config(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResolvedLLMConfig:
    """Load user LLM settings and resolve a valid API key.

    Raises ``HTTPException(400)`` when no API key can be found for the
    configured provider (neither user-stored nor server-level).
    """
    user_settings = await db.scalar(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    provider = user_settings.model_provider if user_settings else "deepseek"
    model_name = user_settings.model_name if user_settings else "deepseek-chat"
    raw_keys = user_settings.api_keys if user_settings else {}
    api_key = resolve_api_key(provider, raw_keys)
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"No API key configured for provider '{provider}'. "
            "Set it in Settings or ask the admin to configure a server-level key.",
        )
    enabled_tools = user_settings.enabled_tools if user_settings else None
    return ResolvedLLMConfig(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        enabled_tools=enabled_tools,
    )
