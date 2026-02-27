import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import decrypt_api_keys, encrypt_api_keys
from app.db.models import User, UserSettings
from app.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_SETTINGS: dict[str, object] = {
    "model_provider": "deepseek",
    "model_name": "deepseek-chat",
    "api_keys": {},
    "persona_override": None,
}


class SettingsUpdate(BaseModel):
    model_provider: str
    model_name: str
    api_keys: dict[str, str] | None = None
    persona_override: str | None = Field(default=None, max_length=2000)


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
        settings.api_keys = encrypt_api_keys(dict(body.api_keys))
    stripped = body.persona_override.strip() if body.persona_override else None
    settings.persona_override = stripped or None
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
    return {
        "model_provider": settings.model_provider,
        "model_name": settings.model_name,
        "api_keys": decrypt_api_keys(settings.api_keys),
        "persona_override": settings.persona_override,
    }
