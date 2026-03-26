import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.core.security import decrypt_api_keys, encrypt_api_keys
from app.db.models import (
    Organization,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceSettings,
)
from app.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class WorkspaceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


def _ws_to_dict(ws: Workspace) -> dict:
    return {
        "id": str(ws.id),
        "name": ws.name,
        "organization_id": str(ws.organization_id),
        "is_deleted": ws.is_deleted,
        "created_at": ws.created_at.isoformat(),
        "updated_at": ws.updated_at.isoformat(),
    }


async def _require_org(user: User, db: AsyncSession) -> Organization:
    """Raise 403 if user has no org."""
    if not user.organization_id:
        raise HTTPException(
            status_code=403, detail="You must belong to an organization"
        )
    org = await db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(status_code=403, detail="Organization not found")
    return org


@router.post("", status_code=201)
@limiter.limit("60/minute")
async def create_workspace(
    request: Request,
    body: WorkspaceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new workspace in the user's organization."""
    org = await _require_org(user, db)
    ws = Workspace(name=body.name, organization_id=org.id)
    db.add(ws)
    await db.commit()
    await db.refresh(ws)
    logger.info("workspace_created", ws_id=str(ws.id), org_id=str(org.id))
    return _ws_to_dict(ws)


@router.get("")
@limiter.limit("60/minute")
async def list_workspaces(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all non-deleted workspaces in the user's organization."""
    if not user.organization_id:
        return []
    rows = await db.scalars(
        select(Workspace).where(
            Workspace.organization_id == user.organization_id,
            Workspace.is_deleted.is_(False),
        )
    )
    return [_ws_to_dict(ws) for ws in rows.all()]


@router.put("/{ws_id}")
@limiter.limit("60/minute")
async def update_workspace(
    request: Request,
    ws_id: uuid.UUID,
    body: WorkspaceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update workspace name. User must belong to the same org."""
    ws = await db.get(Workspace, ws_id)
    if not ws or ws.is_deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")
    ws.name = body.name
    await db.commit()
    return _ws_to_dict(ws)


@router.delete("/{ws_id}", status_code=204)
@limiter.limit("60/minute")
async def delete_workspace(
    request: Request,
    ws_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a workspace. Only org owner may do this."""
    org = await _require_org(user, db)
    ws = await db.get(Workspace, ws_id)
    if not ws or ws.is_deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.organization_id != org.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if org.owner_id != user.id:
        raise HTTPException(
            status_code=403, detail="Only the owner can delete workspaces"
        )
    ws.is_deleted = True
    await db.commit()


@router.get("/{ws_id}/members")
@limiter.limit("60/minute")
async def list_members(
    request: Request,
    ws_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all members of a workspace."""
    ws = await db.get(Workspace, ws_id)
    if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    rows = await db.scalars(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == ws_id)
        .options(selectinload(WorkspaceMember.user))
    )
    return [
        {
            "user_id": str(m.user_id),
            "email": m.user.email if m.user else None,
            "display_name": m.user.display_name if m.user else None,
            "role": m.role,
            "joined_at": m.joined_at.isoformat(),
        }
        for m in rows.all()
    ]


class WorkspaceSettingsUpdate(BaseModel):
    model_provider: str | None = Field(default=None, max_length=50)
    model_name: str | None = Field(default=None, max_length=100)
    api_keys: dict[str, str | list[str]] | None = None


@router.get("/{ws_id}/settings")
@limiter.limit("60/minute")
async def get_workspace_settings(
    request: Request,
    ws_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get LLM settings for a workspace. Membership required."""
    ws = await db.get(Workspace, ws_id)
    if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    membership = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member")
    ws_settings = await db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == ws_id)
    )
    if not ws_settings:
        return {"model_provider": None, "model_name": None, "has_api_key": {}}
    sj = ws_settings.settings_json
    raw_keys = decrypt_api_keys(sj.get("api_keys", {}))
    has_key = {
        provider: bool(v)
        for provider, v in raw_keys.items()
        if v and not provider.startswith("__")
    }
    return {
        "model_provider": sj.get("model_provider"),
        "model_name": sj.get("model_name"),
        "has_api_key": has_key,
    }


@router.put("/{ws_id}/settings")
@limiter.limit("60/minute")
async def update_workspace_settings(
    request: Request,
    ws_id: uuid.UUID,
    body: WorkspaceSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update LLM settings for a workspace. Admin+ only."""
    ws = await db.get(Workspace, ws_id)
    if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    membership = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    ws_settings = await db.scalar(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == ws_id)
    )
    if not ws_settings:
        ws_settings = WorkspaceSettings(workspace_id=ws_id, settings_json={})
        db.add(ws_settings)

    sj = dict(ws_settings.settings_json)
    if body.model_provider is not None:
        sj["model_provider"] = body.model_provider
    if body.model_name is not None:
        sj["model_name"] = body.model_name
    if body.api_keys is not None:
        existing = decrypt_api_keys(sj.get("api_keys", {}))
        existing.update(body.api_keys)
        sj["api_keys"] = encrypt_api_keys(existing)
    ws_settings.settings_json = sj
    await db.commit()
    return {"status": "ok"}
