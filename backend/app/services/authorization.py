"""Centralized authorization helpers.

Consolidates access-control checks previously scattered across API routes
(documents.py, workspaces.py, etc.) into reusable functions.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import Organization, WorkspaceMember

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import Document, User

_PRIVILEGED_ROLES = frozenset({"owner", "admin"})


async def require_org(user: User, db: AsyncSession) -> Organization:
    """Return the user's organization or raise 403."""
    if not user.organization_id:
        raise HTTPException(
            status_code=403, detail="You must belong to an organization"
        )
    org = await db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(status_code=403, detail="Organization not found")
    return org


async def require_workspace_role(
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    allowed_roles: frozenset[str] = _PRIVILEGED_ROLES,
) -> WorkspaceMember:
    """Return membership if user has an allowed role, otherwise raise 403."""
    membership = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if not membership or membership.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Not authorized")
    return membership


async def assert_doc_write_access(
    doc: Document,
    user: User,
    db: AsyncSession,
) -> None:
    """Raise HTTPException if user lacks write permission on a document.

    Workspace documents: allow owner/admin members.
    Personal documents: allow only the original uploader.
    """
    if doc.workspace_id is not None:
        await require_workspace_role(
            workspace_id=doc.workspace_id,
            user_id=user.id,
            db=db,
        )
    elif doc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Document not found")
