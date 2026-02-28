from typing import Literal

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.permissions import DEFAULT_ENABLED_TOOLS, TOOL_NAMES, TOOL_REGISTRY
from app.core.security import decrypt_api_keys, encrypt_api_keys
from app.db.models import User, UserSettings
from app.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

_TOOL_REGISTRY_DICTS = [
    {
        "name": t.name,
        "label": t.label,
        "description": t.description,
        "default_enabled": t.default_enabled,
    }
    for t in TOOL_REGISTRY
]

DEFAULT_SETTINGS: dict[str, object] = {
    "model_provider": "deepseek",
    "model_name": "deepseek-chat",
    "masked_api_keys": {},
    "has_api_key": {},
    "persona_override": None,
    "enabled_tools": DEFAULT_ENABLED_TOOLS,
    "tool_registry": _TOOL_REGISTRY_DICTS,
}


def _mask_key(key: str) -> str:
    """Mask an API key for safe display: show first 3 and last 4 chars."""
    if len(key) > 8:
        return f"{key[:3]}...{key[-4:]}"
    return "****"


class SettingsUpdate(BaseModel):
    model_provider: Literal["deepseek", "openai", "anthropic", "zhipuai"]
    model_name: str = Field(max_length=100)
    api_keys: dict[str, str | list[str]] | None = None
    persona_override: str | None = Field(default=None, max_length=2000)
    enabled_tools: list[str] | None = None


@router.put("")
async def update_settings(
    body: SettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = await db.scalar(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)
    settings.model_provider = body.model_provider
    settings.model_name = body.model_name
    if body.api_keys is not None:
        existing = decrypt_api_keys(settings.api_keys) if settings.api_keys else {}
        existing.update(body.api_keys)
        settings.api_keys = encrypt_api_keys(existing)
    stripped = body.persona_override.strip() if body.persona_override else None
    settings.persona_override = stripped or None
    if body.enabled_tools is not None:
        validated = [t for t in body.enabled_tools if t in TOOL_NAMES]
        settings.enabled_tools = validated
    await db.commit()
    logger.info(
        "settings_updated",
        user_id=str(user.id),
        model_provider=body.model_provider,
        model_name=body.model_name,
        api_keys_updated=body.api_keys is not None,
        persona_updated=body.persona_override is not None,
    )
    return {"status": "ok"}


@router.get("")
async def get_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = await db.scalar(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    if not settings:
        return DEFAULT_SETTINGS
    raw_keys = decrypt_api_keys(settings.api_keys)
    masked: dict[str, list[str]] = {}
    key_counts: dict[str, int] = {}
    for provider, value in raw_keys.items():
        keys = value if isinstance(value, list) else [value] if value else []
        keys = [k for k in keys if k]
        if keys:
            masked[provider] = [_mask_key(k) for k in keys]
            key_counts[provider] = len(keys)
    return {
        "model_provider": settings.model_provider,
        "model_name": settings.model_name,
        "masked_api_keys": masked,
        "key_counts": key_counts,
        "has_api_key": {provider: True for provider in key_counts},
        "persona_override": settings.persona_override,
        "enabled_tools": settings.enabled_tools,
        "tool_registry": _TOOL_REGISTRY_DICTS,
    }
