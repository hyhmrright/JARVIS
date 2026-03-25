"""Conversation folder CRUD."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import ConversationFolder, User
from app.db.session import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/folders", tags=["folders"])


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str | None = Field(default=None, max_length=7)


class FolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: str | None = None
    display_order: int | None = None


class FolderOut(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None = None
    display_order: int
    model_config = {"from_attributes": True}


@router.get("", response_model=list[FolderOut])
async def list_folders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationFolder]:
    result = await db.execute(
        select(ConversationFolder)
        .where(ConversationFolder.user_id == user.id)
        .order_by(ConversationFolder.display_order, ConversationFolder.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=FolderOut, status_code=201)
async def create_folder(
    body: FolderCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationFolder:
    folder = ConversationFolder(
        user_id=user.id,
        name=body.name.strip(),
        color=body.color,
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    logger.info("folder_created", user_id=str(user.id), folder_id=str(folder.id))
    return folder


@router.patch("/{folder_id}", response_model=FolderOut)
async def update_folder(
    folder_id: uuid.UUID,
    body: FolderUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationFolder:
    folder = await db.scalar(
        select(ConversationFolder).where(
            ConversationFolder.id == folder_id,
            ConversationFolder.user_id == user.id,
        )
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    if "name" in body.model_fields_set and body.name:
        folder.name = body.name.strip()
    if "color" in body.model_fields_set:
        folder.color = body.color
    if "display_order" in body.model_fields_set and body.display_order is not None:
        folder.display_order = body.display_order
    await db.commit()
    await db.refresh(folder)
    return folder


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    folder = await db.scalar(
        select(ConversationFolder).where(
            ConversationFolder.id == folder_id,
            ConversationFolder.user_id == user.id,
        )
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    await db.delete(folder)
    await db.commit()
