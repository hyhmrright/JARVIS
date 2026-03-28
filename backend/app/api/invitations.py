import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.db.models import Invitation, User, Workspace, WorkspaceMember
from app.db.session import get_db
from app.services.notifications import create_notification

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["invitations"])

_INVITATION_TTL_HOURS = 72


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern="^(admin|member)$")


class UpdateRoleRequest(BaseModel):
    # "owner" excluded intentionally — ownership transfer is a separate operation
    role: str = Field(pattern="^(admin|member)$")


def _inv_to_dict(inv: Invitation) -> dict:
    return {
        "id": str(inv.id),
        "workspace_id": str(inv.workspace_id),
        "inviter_id": str(inv.inviter_id),
        "email": inv.email,
        "token": str(inv.token),
        "role": inv.role,
        "expires_at": inv.expires_at.isoformat(),
        "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
        "created_at": inv.created_at.isoformat(),
    }


@router.post("/api/workspaces/{ws_id}/members/invite", status_code=201)
@limiter.limit("60/minute")
async def invite_member(
    request: Request,
    ws_id: uuid.UUID,
    body: InviteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create an invitation. The inviter must be admin+ in the workspace."""
    ws = await db.get(Workspace, ws_id)
    if not ws or ws.is_deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if ws.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    membership = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if not membership:
        raise HTTPException(
            status_code=403, detail="You are not a member of this workspace"
        )
    if membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required to invite")

    # Reject if the email already belongs to an active member (case-insensitive).
    email_lower = body.email.lower()
    existing_member = await db.scalar(
        select(WorkspaceMember)
        .join(User, WorkspaceMember.user_id == User.id)
        .where(
            WorkspaceMember.workspace_id == ws_id,
            func.lower(User.email) == email_lower,
        )
    )
    if existing_member:
        raise HTTPException(
            status_code=409, detail="This user is already a member of the workspace"
        )

    # Expire any existing pending invitation for the same (workspace, email) pair
    # to avoid token proliferation (case-insensitive match).
    existing_inv = await db.scalar(
        select(Invitation).where(
            Invitation.workspace_id == ws_id,
            func.lower(Invitation.email) == email_lower,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > datetime.now(UTC),
        )
    )
    if existing_inv:
        existing_inv.expires_at = datetime.now(UTC)

    inv = Invitation(
        workspace_id=ws_id,
        inviter_id=user.id,
        email=body.email,
        role=body.role,
        expires_at=datetime.now(UTC) + timedelta(hours=_INVITATION_TTL_HOURS),
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)

    # 如果受邀用户已存在，发送应用内通知
    target_user = await db.scalar(
        select(User).where(func.lower(User.email) == email_lower)
    )
    if target_user:
        await create_notification(
            user_id=target_user.id,
            type="invitation_received",
            title="New Workspace Invitation",
            body=f"{user.display_name or user.email} invited you to join '{ws.name}'.",
            action_url="/settings",
            metadata={"workspace_id": str(ws_id), "token": str(inv.token)},
            db=db,
        )

    logger.info(
        "invitation_created",
        inv_id=str(inv.id),
        ws_id=str(ws_id),
        email=body.email,
    )
    return _inv_to_dict(inv)


@router.get("/api/invitations/{token}")
@limiter.limit("20/minute")
async def get_invitation(
    request: Request,
    token: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public endpoint: get invitation details by token."""
    inv = await db.scalar(select(Invitation).where(Invitation.token == token))
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if inv.accepted_at:
        raise HTTPException(status_code=410, detail="Invitation already accepted")
    if inv.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Invitation expired")
    ws = await db.get(Workspace, inv.workspace_id)
    return {
        **_inv_to_dict(inv),
        "workspace_name": ws.name if ws and not ws.is_deleted else None,
    }


@router.post("/api/invitations/{token}/accept")
@limiter.limit("60/minute")
async def accept_invitation(
    request: Request,
    token: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Accept an invitation. The JWT user's email must match the invited email."""
    inv = await db.scalar(select(Invitation).where(Invitation.token == token))
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if inv.accepted_at:
        raise HTTPException(status_code=410, detail="Invitation already accepted")
    if inv.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Invitation expired")
    if user.email.lower() != inv.email.lower():
        raise HTTPException(
            status_code=403,
            detail="This invitation is for a different email address",
        )

    # Always validate workspace — user may already have an org but the workspace
    # could have been soft-deleted after the invitation was created.
    ws = await db.get(Workspace, inv.workspace_id)
    if not ws or ws.is_deleted:
        raise HTTPException(status_code=410, detail="Workspace no longer exists")
    if not user.organization_id:
        user.organization_id = ws.organization_id
    elif user.organization_id != ws.organization_id:
        raise HTTPException(
            status_code=403,
            detail="You belong to a different organization",
        )

    existing = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == inv.workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if not existing:
        db.add(
            WorkspaceMember(
                workspace_id=inv.workspace_id,
                user_id=user.id,
                role=inv.role,
            )
        )
    # If already a member (TOCTOU race with invite_member 409 check), preserve
    # existing role rather than silently overwriting it.
    inv.accepted_at = datetime.now(UTC)
    await db.commit()
    logger.info(
        "invitation_accepted",
        inv_id=str(inv.id),
        user_id=str(user.id),
        ws_id=str(inv.workspace_id),
    )
    return {"status": "ok", "workspace_id": str(inv.workspace_id)}


@router.put("/api/workspaces/{ws_id}/members/{member_user_id}")
@limiter.limit("60/minute")
async def update_member_role(
    request: Request,
    ws_id: uuid.UUID,
    member_user_id: uuid.UUID,
    body: UpdateRoleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change a member's role. Admin+ only."""
    ws = await db.get(Workspace, ws_id)
    if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    caller_membership = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if not caller_membership or caller_membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    target = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws_id,
            WorkspaceMember.user_id == member_user_id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    # Prevent stripping ownership without a formal transfer.
    if target.role == "owner" and caller_membership.role != "owner":
        raise HTTPException(
            status_code=403, detail="Only the owner can change another owner's role"
        )
    # Prevent an owner self-demoting and leaving the workspace ownerless.
    if target.user_id == user.id and target.role == "owner":
        raise HTTPException(
            status_code=403,
            detail="Cannot demote yourself as owner; transfer ownership first",
        )
    target.role = body.role
    await db.commit()
    logger.info(
        "member_role_updated",
        ws_id=str(ws_id),
        target_user_id=str(member_user_id),
        new_role=body.role,
        by_user_id=str(user.id),
    )
    return {"status": "ok"}


@router.delete("/api/workspaces/{ws_id}/members/{member_user_id}", status_code=204)
@limiter.limit("60/minute")
async def remove_member(
    request: Request,
    ws_id: uuid.UUID,
    member_user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a member from a workspace. Admin+ or self-removal."""
    ws = await db.get(Workspace, ws_id)
    if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    caller_membership = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    is_self = user.id == member_user_id
    is_admin = caller_membership and caller_membership.role in ("owner", "admin")
    if not is_self and not is_admin:
        raise HTTPException(status_code=403, detail="Permission denied")
    target = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws_id,
            WorkspaceMember.user_id == member_user_id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    # Prevent removing the workspace owner — ownership must be transferred first.
    if target.role == "owner":
        raise HTTPException(
            status_code=403,
            detail="Cannot remove the workspace owner; transfer ownership first",
        )
    await db.delete(target)
    await db.commit()
    logger.info(
        "member_removed",
        ws_id=str(ws_id),
        removed_user_id=str(member_user_id),
        by_user_id=str(user.id),
    )
