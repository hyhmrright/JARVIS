"""Plugin management API — list, install, config, and RBAC."""

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user
from app.db.models import PluginConfig, User, UserSettings
from app.db.session import get_db
from app.plugins import plugin_registry
from app.plugins.loader import activate_all_plugins, install_plugin_from_url
from app.services.skill_market import MarketSkill, skill_market_manager

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("/market/skills", response_model=list[MarketSkill])
async def list_market_skills(
    user: User = Depends(get_current_user),
) -> list[MarketSkill]:
    """Fetch available skills from the remote registry."""
    return await skill_market_manager.fetch_registry()


@router.post("/market/install/{skill_id}")
async def install_market_skill(
    skill_id: str,
    md_url: str,
    admin: User = Depends(get_admin_user),
) -> dict[str, str]:
    """Download and install a skill from the market."""
    success = await skill_market_manager.install_skill(skill_id, md_url)
    if not success:
        raise HTTPException(status_code=400, detail="Skill installation failed")

    # Trigger hot-reload
    from app.plugins.loader import deactivate_all_plugins, load_all_plugins

    await deactivate_all_plugins(plugin_registry)
    plugin_registry._entries.clear()
    await load_all_plugins(plugin_registry)
    await activate_all_plugins(plugin_registry)

    return {"status": "ok"}


@router.delete("/market/uninstall/{skill_id}")
async def uninstall_market_skill(
    skill_id: str,
    admin: User = Depends(get_admin_user),
) -> dict[str, str]:
    """Remove an installed skill."""
    success = skill_market_manager.uninstall_skill(skill_id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Skill not found or already uninstalled"
        )

    # Trigger hot-reload
    from app.plugins.loader import deactivate_all_plugins, load_all_plugins

    await deactivate_all_plugins(plugin_registry)
    plugin_registry._entries.clear()
    await load_all_plugins(plugin_registry)
    await activate_all_plugins(plugin_registry)

    return {"status": "ok"}


@router.post("/reload")
async def reload_plugins(
    admin: User = Depends(get_admin_user),
) -> dict[str, str]:
    """Hot-reload all plugins (Admin only)."""
    import sys

    from app.plugins.loader import deactivate_all_plugins, load_all_plugins

    await deactivate_all_plugins(plugin_registry)

    # Clear current registry entries
    plugin_registry._entries.clear()

    # Clear user plugins from sys.modules to force reload
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("jarvis_user_plugins."):
            sys.modules.pop(mod_name, None)

    await load_all_plugins(plugin_registry)
    await activate_all_plugins(plugin_registry)

    return {"status": "ok"}


# ── Install ────────────────────────────────────────────────────────────────────


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
        await activate_all_plugins(plugin_registry)
        return {"status": "ok", "plugin_id": plugin_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Installation failed: {e}") from e


# ── List ───────────────────────────────────────────────────────────────────────


class PluginInfo(BaseModel):
    plugin_id: str
    name: str
    version: str
    description: str
    tools: list[str]
    channels: list[str]
    config_schema: dict[str, Any] | None = None
    requires: list[str] = []


@router.get("", response_model=list[PluginInfo])
async def list_plugins(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PluginInfo]:
    """Return metadata for plugins this user has access to.

    Admin/superadmin users see all plugins. Regular users see only the plugins
    their admin has granted them access to via plugin_permissions.
    """
    all_plugins = plugin_registry.list_plugins()
    if user.role in ("admin", "superadmin"):
        return [PluginInfo(**p) for p in all_plugins]
    us = await db.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    allowed = set(us.plugin_permissions if us else [])
    return [PluginInfo(**p) for p in all_plugins if p["plugin_id"] in allowed]


# ── RBAC: per-user plugin permissions (admin only) ────────────────────────────


class PluginPermissionsUpdate(BaseModel):
    plugin_ids: list[str]


@router.put("/users/{target_user_id}/permissions", response_model=None)
async def set_user_plugin_permissions(
    target_user_id: uuid.UUID,
    body: PluginPermissionsUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Admin grants/revokes a user's access to specific plugins."""
    us = await db.scalar(
        select(UserSettings).where(UserSettings.user_id == target_user_id)
    )
    if not us:
        raise HTTPException(status_code=404, detail="User settings not found")
    us.plugin_permissions = body.plugin_ids
    await db.commit()
    return {
        "status": "ok",
        "user_id": str(target_user_id),
        "plugin_ids": body.plugin_ids,
    }


@router.get("/users/{target_user_id}/permissions", response_model=None)
async def get_user_plugin_permissions(
    target_user_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Admin reads a user's current plugin permissions."""
    us = await db.scalar(
        select(UserSettings).where(UserSettings.user_id == target_user_id)
    )
    return {
        "user_id": str(target_user_id),
        "plugin_ids": us.plugin_permissions if us else [],
    }


# ── Plugin Config CRUD ─────────────────────────────────────────────────────────


class ConfigSetRequest(BaseModel):
    key: str
    value: str
    is_secret: bool = False


class ConfigItem(BaseModel):
    key: str
    value: str
    is_secret: bool


@router.put("/{plugin_id}/config", response_model=ConfigItem)
async def set_plugin_config(
    plugin_id: str,
    body: ConfigSetRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConfigItem:
    """Upsert a single config key for the current user + plugin."""
    existing = await db.scalar(
        select(PluginConfig).where(
            PluginConfig.user_id == user.id,
            PluginConfig.plugin_id == plugin_id,
            PluginConfig.key == body.key,
        )
    )
    if existing:
        existing.value = body.value
        existing.is_secret = body.is_secret
    else:
        db.add(
            PluginConfig(
                user_id=user.id,
                plugin_id=plugin_id,
                key=body.key,
                value=body.value,
                is_secret=body.is_secret,
            )
        )
    await db.commit()
    return ConfigItem(key=body.key, value=body.value, is_secret=body.is_secret)


@router.get("/{plugin_id}/config", response_model=None)
async def get_plugin_config(
    plugin_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return all config for current user + plugin. Secret values are masked."""
    rows = await db.scalars(
        select(PluginConfig).where(
            PluginConfig.user_id == user.id,
            PluginConfig.plugin_id == plugin_id,
        )
    )
    return {
        row.key: {
            "value": "***" if row.is_secret else row.value,
            "is_secret": row.is_secret,
        }
        for row in rows.all()
    }


@router.delete("/{plugin_id}/config/{key}", response_model=None)
async def delete_plugin_config(
    plugin_id: str,
    key: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete a single config key for the current user + plugin."""
    await db.execute(
        delete(PluginConfig).where(
            PluginConfig.user_id == user.id,
            PluginConfig.plugin_id == plugin_id,
            PluginConfig.key == key,
        )
    )
    await db.commit()
    return {"status": "ok"}
