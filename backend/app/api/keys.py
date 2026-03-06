"""Personal API Keys (PAT) management endpoints."""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import ApiKey, User
from app.db.session import get_db

router = APIRouter(prefix="/api/keys", tags=["keys"])

_MAX_KEYS_PER_USER = 10


def _generate_pat() -> str:
    """Generate a new Personal Access Token: jv_ + 64 hex chars (32 random bytes)."""
    return "jv_" + os.urandom(32).hex()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class ApiKeyCreate(BaseModel):
    name: str
    scope: str = "full"
    expires_at: datetime | None = None


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


@router.post("", response_model=ApiKeyCreateResponse, status_code=201)
async def create_key(
    body: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    """Create a new Personal Access Token.

    The raw key is returned **once** and never stored.
    Raises 422 if scope is not 'full' or 'readonly'.
    Raises 409 if the user already has 10 active keys.
    """
    if body.scope not in ("full", "readonly"):
        raise HTTPException(
            status_code=422, detail="scope must be 'full' or 'readonly'"
        )

    count = await db.scalar(
        select(func.count()).select_from(ApiKey).where(ApiKey.user_id == user.id)
    )
    if (count or 0) >= _MAX_KEYS_PER_USER:
        raise HTTPException(
            status_code=409,
            detail=f"Maximum of {_MAX_KEYS_PER_USER} API keys per user reached",
        )

    raw_key = _generate_pat()
    api_key = ApiKey(
        user_id=user.id,
        name=body.name,
        key_hash=_hash_token(raw_key),
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
async def list_keys(
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
    return [
        ApiKeyItem(
            id=k.id,
            name=k.name,
            prefix=k.prefix,
            scope=k.scope,
            expires_at=k.expires_at,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=204)
async def delete_key(
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
