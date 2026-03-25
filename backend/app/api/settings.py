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
from app.infra.ollama import get_ollama_models

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

# Static models for cloud providers
PROVIDER_MODELS: dict[str, list[str]] = {
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "openai": ["gpt-4o-mini", "gpt-4o", "o1-mini", "o3-mini"],
    "anthropic": ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"],
    "zhipuai": [
        "glm-4-flash",
        "glm-4",
        "glm-4-plus",
        "glm-4.5",
        "glm-4.7",
        "glm-4.7-FlashX",
        "glm-5",
        "glm-z1-flash",
    ],
}

DEFAULT_SETTINGS: dict[str, object] = {
    "model_provider": "deepseek",
    "model_name": "deepseek-chat",
    "masked_api_keys": {},
    "has_api_key": {},
    "persona_override": None,
    "enabled_tools": DEFAULT_ENABLED_TOOLS,
    "tool_registry": _TOOL_REGISTRY_DICTS,
    "temperature": 0.7,
    "max_tokens": None,
    "system_prompt": None,
}


def _mask_key(key: str) -> str:
    """Mask an API key for safe display: show first 3 and last 4 chars."""
    if len(key) > 8:
        return f"{key[:3]}...{key[-4:]}"
    return "****"


class SettingsUpdate(BaseModel):
    model_provider: (
        Literal["deepseek", "openai", "anthropic", "zhipuai", "ollama"] | None
    ) = None
    model_name: str | None = Field(default=None, max_length=100)
    api_keys: dict[str, str | list[str]] | None = None
    persona_override: str | None = Field(default=None, max_length=2000)
    enabled_tools: list[str] | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    system_prompt: str | None = Field(default=None, max_length=4000)


@router.get("/models")
async def list_available_models() -> dict[str, list[str]]:
    """Return all available LLM models for each provider."""
    all_models = PROVIDER_MODELS.copy()
    try:
        # Dynamic discovery for local Ollama models
        ollama_models = await get_ollama_models()
        all_models["ollama"] = ollama_models
    except Exception:
        logger.warning("ollama_discovery_failed", exc_info=True)
        all_models["ollama"] = []
    return all_models


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

    if "model_provider" in body.model_fields_set and body.model_provider:
        settings.model_provider = body.model_provider
    if "model_name" in body.model_fields_set and body.model_name:
        settings.model_name = body.model_name

    if body.api_keys is not None:
        existing = decrypt_api_keys(settings.api_keys) if settings.api_keys else {}
        existing.update(body.api_keys)
        settings.api_keys = encrypt_api_keys(existing)

    if "persona_override" in body.model_fields_set:
        stripped = body.persona_override.strip() if body.persona_override else None
        settings.persona_override = stripped or None

    if body.enabled_tools is not None:
        validated = [t for t in body.enabled_tools if t in TOOL_NAMES]
        settings.enabled_tools = validated

    if "temperature" in body.model_fields_set and body.temperature is not None:
        settings.temperature = body.temperature
    if "max_tokens" in body.model_fields_set:
        settings.max_tokens = body.max_tokens  # None 表示清除为模型默认值
    if "system_prompt" in body.model_fields_set:
        stripped_sp = body.system_prompt.strip() if body.system_prompt else None
        settings.system_prompt = stripped_sp or None

    await db.commit()
    logger.info(
        "settings_updated",
        user_id=str(user.id),
        model_provider=settings.model_provider,
        model_name=settings.model_name,
        api_keys_updated=body.api_keys is not None,
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
        "ollama_base_url": raw_keys.get("ollama_base_url"),
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "system_prompt": settings.system_prompt,
    }
