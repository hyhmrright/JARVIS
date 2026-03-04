"""Plugin management API — list and install plugins."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_admin_user, get_current_user
from app.db.models import User
from app.plugins import plugin_registry
from app.plugins.loader import activate_all_plugins, install_plugin_from_url

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


class InstallRequest(BaseModel):
    url: str


@router.post("/install")
async def install_plugin(
    body: InstallRequest,
    admin: User = Depends(get_admin_user),
) -> dict[str, str]:
    """Install a new plugin from a raw Python file URL (OpenClaw style)."""
    try:
        plugin_id = await install_plugin_from_url(body.url, plugin_registry)
        # Re-activate to ensure on_load is called for the new plugin
        await activate_all_plugins(plugin_registry)
        return {"status": "ok", "plugin_id": plugin_id}
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Installation failed: {str(e)}"
        ) from e


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
