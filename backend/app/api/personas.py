import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import Persona, User
from app.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/personas", tags=["personas"])


class PersonaCreate(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str


class PersonaOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    system_prompt: str
    model_config = {"from_attributes": True}


@router.get("", response_model=list[PersonaOut])
async def list_personas(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = await db.scalars(
        select(Persona).where(Persona.user_id == user.id).order_by(Persona.name)
    )
    return rows.all()


@router.post("", response_model=PersonaOut, status_code=201)
async def create_persona(
    body: PersonaCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    new_persona = Persona(
        user_id=user.id,
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
    )
    db.add(new_persona)
    await db.commit()
    await db.refresh(new_persona)
    return new_persona


@router.delete("/{persona_id}")
async def delete_persona(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    persona = await db.scalar(
        select(Persona).where(Persona.id == persona_id, Persona.user_id == user.id)
    )
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    await db.delete(persona)
    await db.commit()
    return {"status": "ok"}
