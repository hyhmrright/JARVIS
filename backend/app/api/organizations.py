import re
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.db.models import Organization, User
from app.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/organizations", tags=["organizations"])

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,98}[a-z0-9]$")


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=3, max_length=100)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "slug must be 3-100 lowercase alphanumeric chars or hyphens, "
                "starting and ending with alphanumeric"
            )
        return v


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=3, max_length=100)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None and not _SLUG_RE.match(v):
            raise ValueError("invalid slug format")
        return v


def _org_to_dict(org: Organization) -> dict:
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "owner_id": str(org.owner_id),
        "created_at": org.created_at.isoformat(),
    }


@router.post("", status_code=201)
@limiter.limit("60/minute")
async def create_organization(
    request: Request,
    body: OrgCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new organization. The caller becomes the owner."""
    existing_slug = await db.scalar(
        select(Organization).where(Organization.slug == body.slug)
    )
    if existing_slug:
        raise HTTPException(status_code=409, detail="Slug already taken")
    org = Organization(name=body.name, slug=body.slug, owner_id=user.id)
    db.add(org)
    await db.flush()
    user.organization_id = org.id
    await db.commit()
    logger.info("organization_created", org_id=str(org.id), owner_id=str(user.id))
    return _org_to_dict(org)


@router.get("/me")
@limiter.limit("60/minute")
async def get_my_organization(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the organization the current user belongs to."""
    if not user.organization_id:
        raise HTTPException(status_code=404, detail="Not a member of any organization")
    org = await db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _org_to_dict(org)


@router.delete("/{org_id}", status_code=204)
@limiter.limit("20/minute")
async def delete_organization(
    request: Request,
    org_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an organization. Only the owner may do this."""
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if org.owner_id != user.id:
        raise HTTPException(
            status_code=403, detail="Only the owner can delete the organization"
        )
    await db.delete(org)
    await db.commit()
    logger.info("organization_deleted", org_id=str(org_id), owner_id=str(user.id))


@router.put("/{org_id}")
@limiter.limit("60/minute")
async def update_organization(
    request: Request,
    org_id: uuid.UUID,
    body: OrgUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update org name or slug. Only the org owner may do this."""
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if org.owner_id != user.id:
        raise HTTPException(
            status_code=403, detail="Only the owner can update the organization"
        )
    if body.name is not None:
        org.name = body.name
    if body.slug is not None:
        clash = await db.scalar(
            select(Organization).where(
                Organization.slug == body.slug, Organization.id != org_id
            )
        )
        if clash:
            raise HTTPException(status_code=409, detail="Slug already taken")
        org.slug = body.slug
    await db.commit()
    return _org_to_dict(org)
