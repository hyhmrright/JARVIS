import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.models import Organization, User, Workspace, WorkspaceMember
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
async def create_workspace(
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
async def list_workspaces(
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
async def update_workspace(
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
async def delete_workspace(
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
async def list_members(
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
