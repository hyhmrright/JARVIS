"""Plugin management API — list installed plugins."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.db.models import User
from app.plugins import plugin_registry

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


class PluginInfo(BaseModel):
    id: str
    name: str
    version: str
    description: str
    tools: list[str]
    channels: list[str]


@router.get("", response_model=list[PluginInfo])
async def list_plugins(
    _user: User = Depends(get_current_user),
) -> list[PluginInfo]:
    """Return metadata for all loaded plugins."""
    return [PluginInfo(**p) for p in plugin_registry.list_plugins()]
