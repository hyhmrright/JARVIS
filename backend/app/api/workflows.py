import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User, Workflow
from app.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    dsl: dict


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


@router.post("", response_model=WorkflowOut, status_code=201)
async def create_workflow(
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


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    workflow = await db.scalar(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user.id)
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    await db.delete(workflow)
    await db.commit()
    return {"status": "ok"}
