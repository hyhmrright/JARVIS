"""Personal API Keys (PAT) management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.core.security import generate_api_key, hash_api_key
from app.db.models import ApiKey, User
from app.db.session import get_db

router = APIRouter(prefix="/api/keys", tags=["keys"])

_MAX_KEYS_PER_USER = 10


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    scope: Literal["full", "readonly"] = "full"
    expires_at: datetime | None = None


class ApiKeyRename(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    scope: str
    raw_key: str  # shown once only
    expires_at: datetime | None
    created_at: datetime


class ApiKeyItem(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    scope: str
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


@router.post("", response_model=ApiKeyCreateResponse, status_code=201)
@limiter.limit("10/minute")
async def create_key(
    request: Request,
    body: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    """Create a new Personal Access Token.

    The raw key is returned **once** and never stored.
    Raises 409 if the user already has 10 active keys.
    """
    count = await db.scalar(
        select(func.count()).select_from(ApiKey).where(ApiKey.user_id == user.id)
    )
    if (count or 0) >= _MAX_KEYS_PER_USER:
        raise HTTPException(
            status_code=409,
            detail=f"Maximum of {_MAX_KEYS_PER_USER} API keys per user reached",
        )

    raw_key = generate_api_key()
    api_key = ApiKey(
        user_id=user.id,
        name=body.name,
        key_hash=hash_api_key(raw_key),
        prefix=raw_key[:8],  # first 8 chars of the raw token
        scope=body.scope,
        expires_at=body.expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        scope=api_key.scope,
        raw_key=raw_key,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[ApiKeyItem])
@limiter.limit("60/minute")
async def list_keys(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    """List all API keys for the current user (no raw tokens)."""
    result = await db.scalars(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.all()
    return [ApiKeyItem.model_validate(k) for k in keys]


@router.patch("/{key_id}", response_model=ApiKeyItem)
@limiter.limit("20/minute")
async def rename_key(
    request: Request,
    key_id: uuid.UUID,
    body: ApiKeyRename,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    """Rename an API key."""
    api_key = await db.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.name = body.name
    await db.commit()
    return ApiKeyItem.model_validate(api_key)


@router.delete("/{key_id}", status_code=204)
@limiter.limit("30/minute")
async def delete_key(
    request: Request,
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Revoke an API key by ID. Returns 404 if not found or belongs to another user."""
    api_key = await db.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    await db.delete(api_key)
    await db.commit()
