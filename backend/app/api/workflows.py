import copy
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.db.models import User, Workflow
from app.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


async def _get_workflow_or_404(
    db: AsyncSession, workflow_id: uuid.UUID, user_id: uuid.UUID
) -> Workflow:
    workflow = await db.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    dsl: dict = Field(default_factory=dict)


class WorkflowOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    dsl: dict
    model_config = {"from_attributes": True}


@router.get("", response_model=list[WorkflowOut])
async def list_workflows(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    rows = await db.scalars(
        select(Workflow).where(Workflow.user_id == user.id).order_by(Workflow.name)
    )
    return rows.all()


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await _get_workflow_or_404(db, workflow_id, user.id)


@router.post("", response_model=WorkflowOut, status_code=201)
@limiter.limit("20/minute")
async def create_workflow(
    request: Request,
    body: WorkflowCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    new_workflow = Workflow(
        user_id=user.id,
        name=body.name,
        description=body.description,
        dsl=body.dsl,
    )
    db.add(new_workflow)
    await db.commit()
    await db.refresh(new_workflow)
    return new_workflow


@router.put("/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    workflow_id: uuid.UUID,
    body: WorkflowCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    workflow = await _get_workflow_or_404(db, workflow_id, user.id)
    workflow.name = body.name
    workflow.description = body.description
    workflow.dsl = body.dsl
    await db.commit()
    await db.refresh(workflow)
    return workflow


@router.post("/{workflow_id}/clone", response_model=WorkflowOut, status_code=201)
@limiter.limit("20/minute")
async def clone_workflow(
    request: Request,
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    workflow = await _get_workflow_or_404(db, workflow_id, user.id)
    base_name = workflow.name.removesuffix(" (copy)")
    clone = Workflow(
        user_id=user.id,
        name=f"{base_name} (copy)",
        description=workflow.description,
        dsl=copy.deepcopy(workflow.dsl),
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return clone


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    workflow = await _get_workflow_or_404(db, workflow_id, user.id)
    await db.delete(workflow)
    await db.commit()
    return {"status": "ok"}
