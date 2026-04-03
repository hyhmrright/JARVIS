"""Workspace business logic — extracted from api/workspaces.py."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from fastapi import HTTPException

from app.db.models import Workspace
from app.services.authorization import require_org, require_workspace_role

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import User

logger = structlog.get_logger(__name__)


class WorkspaceService:
    """Domain service for Workspace lifecycle operations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_workspace(self, *, user: User, name: str) -> Workspace:
        """Create a new workspace in the user's organization."""
        org = await require_org(user, self._db)
        ws = Workspace(name=name, organization_id=org.id)
        self._db.add(ws)
        await self._db.commit()
        await self._db.refresh(ws)
        logger.info("workspace_created", ws_id=str(ws.id), org_id=str(org.id))
        return ws

    async def update_workspace(
        self,
        *,
        ws_id: uuid.UUID,
        user: User,
        name: str,
    ) -> Workspace:
        """Update workspace name. Requires owner/admin role."""
        ws: Workspace | None = await self._db.get(Workspace, ws_id)
        if not ws or ws.is_deleted:
            raise HTTPException(status_code=404, detail="Workspace not found")
        if ws.organization_id != user.organization_id:
            raise HTTPException(status_code=403, detail="Access denied")
        await require_workspace_role(workspace_id=ws_id, user_id=user.id, db=self._db)
        ws.name = name
        await self._db.commit()
        return ws

    async def delete_workspace(
        self,
        *,
        ws_id: uuid.UUID,
        user: User,
    ) -> None:
        """Soft-delete a workspace. Only the org owner may do this."""
        org = await require_org(user, self._db)
        ws = await self._db.get(Workspace, ws_id)
        if not ws or ws.is_deleted:
            raise HTTPException(status_code=404, detail="Workspace not found")
        if ws.organization_id != org.id:
            raise HTTPException(status_code=403, detail="Access denied")
        if org.owner_id != user.id:
            raise HTTPException(
                status_code=403, detail="Only the owner can delete workspaces"
            )
        ws.soft_delete()
        await self._db.commit()
