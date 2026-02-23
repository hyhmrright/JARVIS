from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import decrypt_api_keys, encrypt_api_keys
from app.db.models import User, UserSettings
from app.db.session import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_SETTINGS: dict = {
    "model_provider": "deepseek",
    "model_name": "deepseek-chat",
    "api_keys": {},
}


class SettingsUpdate(BaseModel):
    model_provider: str
    model_name: str
    api_keys: dict[str, str]


@router.put("")
async def update_settings(
    body: SettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    s = await db.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    if not s:
        s = UserSettings(user_id=user.id)
        db.add(s)
    s.model_provider = body.model_provider
    s.model_name = body.model_name
    s.api_keys = encrypt_api_keys(dict(body.api_keys))
    await db.commit()
    return {"status": "ok"}


@router.get("")
async def get_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    s = await db.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    if not s:
        return DEFAULT_SETTINGS
    return {
        "model_provider": s.model_provider,
        "model_name": s.model_name,
        "api_keys": decrypt_api_keys(s.api_keys),
    }
