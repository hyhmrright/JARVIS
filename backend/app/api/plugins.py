"""Plugin management API — list installed plugins."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_admin_user, get_current_user
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


@router.post("/{plugin_id}/enable")
async def enable_plugin(
    plugin_id: str,
    enable: bool = True,
    admin: User = Depends(get_admin_user),
) -> dict[str, str]:
    """Globally enable or disable a plugin (placeholder: needs registry support)."""
    return {"status": "ok", "plugin_id": plugin_id, "enabled": str(enable)}


@router.get("/config")
async def get_all_plugin_configs(
    admin: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Return global configuration for all plugins (placeholder)."""
    return {"configs": {}}
