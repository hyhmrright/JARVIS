import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.db.models import Persona, User
from app.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/personas", tags=["personas"])


async def _get_persona_or_404(
    db: AsyncSession, persona_id: uuid.UUID, user_id: uuid.UUID
) -> Persona:
    persona = await db.scalar(
        select(Persona).where(Persona.id == persona_id, Persona.user_id == user_id)
    )
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


class PersonaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    system_prompt: str = Field(min_length=1, max_length=8000)


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
@limiter.limit("20/minute")
async def create_persona(
    request: Request,
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


@router.put("/{persona_id}", response_model=PersonaOut)
@limiter.limit("20/minute")
async def update_persona(
    request: Request,
    persona_id: uuid.UUID,
    body: PersonaCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    persona = await _get_persona_or_404(db, persona_id, user.id)
    persona.name = body.name
    persona.description = body.description
    persona.system_prompt = body.system_prompt
    await db.commit()
    await db.refresh(persona)
    return persona


@router.post("/{persona_id}/clone", response_model=PersonaOut, status_code=201)
@limiter.limit("20/minute")
async def clone_persona(
    request: Request,
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    persona = await _get_persona_or_404(db, persona_id, user.id)
    base_name = persona.name.removesuffix(" (copy)")
    clone = Persona(
        user_id=user.id,
        name=f"{base_name} (copy)",
        description=persona.description,
        system_prompt=persona.system_prompt,
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return clone


@router.delete("/{persona_id}")
@limiter.limit("30/minute")
async def delete_persona(
    request: Request,
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    persona = await _get_persona_or_404(db, persona_id, user.id)
    await db.delete(persona)
    await db.commit()
    return {"status": "ok"}
