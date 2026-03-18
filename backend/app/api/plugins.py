"""Plugin management API — list, install, config, and RBAC."""

import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user
from app.core.config import settings
from app.db.models import InstalledPlugin, PluginConfig, User, UserSettings
from app.db.session import get_db
from app.plugins import plugin_registry
from app.plugins.adapters.mcp import parse_mcp_command
from app.plugins.adapters.python_plugin import download_python_plugin
from app.plugins.adapters.skill_md import download_skill_md, extract_md_title
from app.plugins.loader import activate_all_plugins, reload_system_plugins
from app.plugins.type_detector import detect_type
from app.services.skill_market import MarketSkillOut, skill_market_manager

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/plugins", tags=["plugins"])


# ── Schemas ────────────────────────────────────────────────────────────────────


class InstallRequest(BaseModel):
    url: str
    type: Literal["mcp", "skill_md", "python_plugin"] | None = None
    scope: Literal["system", "personal"]


class InstalledPluginOut(BaseModel):
    id: str
    plugin_id: str
    name: str
    type: str
    install_url: str
    scope: str
    installed_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Market ─────────────────────────────────────────────────────────────────────


@router.get("/market/skills", response_model=list[MarketSkillOut])
async def list_market_skills(
    user: User = Depends(get_current_user),
) -> list[MarketSkillOut]:
    """Fetch available skills from the local registry."""
    return await skill_market_manager.fetch_registry()


# ── Detect ─────────────────────────────────────────────────────────────────────


@router.get("/detect")
async def detect_plugin_type(
    url: str,
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Auto-detect plugin type from a URL or npx command."""
    result = detect_type(url)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail={
                "msg": "Cannot determine type",
                "candidates": ["mcp", "skill_md", "python_plugin"],
            },
        )
    return {"type": result.type}


# ── Install helpers ────────────────────────────────────────────────────────────


def _safe_plugin_id(raw: str) -> str:
    """Sanitize a plugin_id to only contain [a-z0-9-]."""
    return re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-")


def _resolve_detection(
    req: InstallRequest,
) -> tuple[str, str, str]:
    """Return (detected_type, plugin_id, default_name) or raise HTTPException."""
    detection = detect_type(req.url)
    if req.type:
        raw_id = (
            detection.plugin_id if detection else req.url.split("/")[-1].split(".")[0]
        )
        plugin_id = _safe_plugin_id(raw_id)
        default_name = (
            detection.default_name if detection else plugin_id.replace("-", " ").title()
        )
        return req.type, plugin_id, default_name

    if detection is None:
        raise HTTPException(
            status_code=422,
            detail={
                "msg": "Cannot determine type",
                "candidates": ["mcp", "skill_md", "python_plugin"],
            },
        )
    return detection.type, _safe_plugin_id(detection.plugin_id), detection.default_name


def _scope_dir(scope: str, user_id: Any, base: Path) -> Path:
    """Resolve the filesystem directory for a given scope."""
    return base / "system" if scope == "system" else base / "users" / str(user_id)


async def _fetch_file_plugin(
    detected_type: str,
    req: InstallRequest,
    plugin_id: str,
    default_name: str,
    user_id: Any,
) -> str:
    """Download skill_md / python_plugin files; return resolved display name."""
    base = Path(settings.installed_plugins_dir)
    scope_dir = _scope_dir(req.scope, user_id, base)
    name = default_name
    try:
        if detected_type == "skill_md":
            content = await download_skill_md(req.url, scope_dir / f"{plugin_id}.md")
            md_title = extract_md_title(content)
            if md_title:
                name = md_title
        elif detected_type == "python_plugin":
            _, manifest_name = await download_python_plugin(req.url, scope_dir)
            if manifest_name:
                name = manifest_name
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {e}") from e
    return name


# ── Install ────────────────────────────────────────────────────────────────────


@router.post("/install", response_model=InstalledPluginOut)
async def install_plugin_unified(
    req: InstallRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InstalledPlugin:
    """Install a plugin/skill from a URL or npx command."""
    if req.scope == "system" and user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin required for system scope")

    detected_type, plugin_id, default_name = _resolve_detection(req)

    # Duplicate check (application-level; mirrors the DB partial unique indexes)
    dup_filter = [
        InstalledPlugin.plugin_id == plugin_id,
        InstalledPlugin.scope == req.scope,
    ]
    if req.scope == "personal":
        dup_filter.append(InstalledPlugin.installed_by == user.id)
    if await db.scalar(select(InstalledPlugin).where(*dup_filter)):
        raise HTTPException(status_code=409, detail="Already installed")

    mcp_command: str | None = None
    mcp_args: list[str] | None = None
    name = default_name

    if detected_type == "mcp":
        mcp_command, mcp_args = parse_mcp_command(req.url)
    else:
        name = await _fetch_file_plugin(
            detected_type, req, plugin_id, default_name, user.id
        )

    installed_by = None if req.scope == "system" else user.id
    row = InstalledPlugin(
        plugin_id=plugin_id,
        name=name,
        type=detected_type,
        install_url=req.url,
        mcp_command=mcp_command,
        mcp_args=mcp_args,
        scope=req.scope,
        installed_by=installed_by,
    )
    db.add(row)
    try:
        await db.commit()
        await db.refresh(row)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Already installed") from None

    if req.scope == "system":
        await reload_system_plugins(plugin_registry)

    return row


# ── Uninstall ──────────────────────────────────────────────────────────────────


@router.delete("/install/{installed_plugin_id}", status_code=204)
async def uninstall_plugin(
    installed_plugin_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Uninstall a plugin. Admin for system scope; owner for personal scope."""
    result = await db.execute(
        select(InstalledPlugin).where(InstalledPlugin.id == installed_plugin_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    if row.scope == "system" and user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    if row.scope == "personal" and row.installed_by != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if row.type in ("skill_md", "python_plugin"):
        if row.scope == "personal" and row.installed_by is None:
            logger.error("uninstall_missing_installed_by", plugin_id=row.plugin_id)
        else:
            inst_dir = Path(settings.installed_plugins_dir)
            base = (
                inst_dir / "system"
                if row.scope == "system"
                else inst_dir / "users" / str(row.installed_by)
            )
            for candidate in [
                base / f"{row.plugin_id}.md",
                base / f"{row.plugin_id}.py",
                base / row.plugin_id,
            ]:
                if candidate.exists():
                    if candidate.is_dir():
                        shutil.rmtree(candidate)
                    else:
                        candidate.unlink()
                    break

    await db.delete(row)
    await db.commit()
    if row.scope == "system":
        await reload_system_plugins(plugin_registry)


# ── List installed ─────────────────────────────────────────────────────────────


@router.get("/installed")
async def list_installed_plugins(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[InstalledPluginOut]]:
    """List installed plugins: system (all users) + personal (own only)."""
    system_result = await db.execute(
        select(InstalledPlugin).where(InstalledPlugin.scope == "system")
    )
    personal_result = await db.execute(
        select(InstalledPlugin).where(
            InstalledPlugin.scope == "personal",
            InstalledPlugin.installed_by == user.id,
        )
    )
    return {
        "system": [
            InstalledPluginOut.model_validate(r) for r in system_result.scalars().all()
        ],
        "personal": [
            InstalledPluginOut.model_validate(r)
            for r in personal_result.scalars().all()
        ],
    }


# ── Reload ─────────────────────────────────────────────────────────────────────


@router.post("/reload")
async def reload_plugins_endpoint(
    admin: User = Depends(get_admin_user),
) -> dict[str, str]:
    """Hot-reload all plugins (Admin only)."""
    import sys

    from app.plugins.loader import deactivate_all_plugins, load_all_plugins

    await deactivate_all_plugins(plugin_registry)
    plugin_registry._entries.clear()
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("jarvis_user_plugins."):
            sys.modules.pop(mod_name, None)
    await load_all_plugins(plugin_registry)
    await activate_all_plugins(plugin_registry)
    return {"status": "ok"}


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
    """Return metadata for plugins this user has access to."""
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
