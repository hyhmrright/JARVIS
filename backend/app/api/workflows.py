from __future__ import annotations

import copy
import uuid
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_validator
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


# ---------------------------------------------------------------------------
# DSL node schemas (discriminated union on `type`)
# ---------------------------------------------------------------------------


class _InputNodeDef(BaseModel):
    id: str
    type: Literal["input"]
    data: dict[str, Any] = {}


class _LLMNodeDef(BaseModel):
    id: str
    type: Literal["llm"]
    data: dict[str, Any] = {}


class _ToolNodeDef(BaseModel):
    id: str
    type: Literal["tool"]
    data: dict[str, Any] = {}


class _ConditionNodeDef(BaseModel):
    id: str
    type: Literal["condition"]
    data: dict[str, Any] = {}


class _OutputNodeDef(BaseModel):
    id: str
    type: Literal["output"]
    data: dict[str, Any] = {}


class _ImageGenNodeDef(BaseModel):
    id: str
    type: Literal["image_gen"]
    data: dict[str, Any] = {}


_NodeDef = Annotated[
    _InputNodeDef
    | _LLMNodeDef
    | _ToolNodeDef
    | _ConditionNodeDef
    | _OutputNodeDef
    | _ImageGenNodeDef,
    Field(discriminator="type"),
]


class _EdgeDef(BaseModel):
    model_config = {"populate_by_name": True}

    id: str
    source: str
    target: str
    source_handle: str | None = Field(default=None, alias="sourceHandle")
    target_handle: str | None = Field(default=None, alias="targetHandle")


def _build_adjacency(nodes: list[Any], edges: list[_EdgeDef]) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {n.id: [] for n in nodes}
    for edge in edges:
        adj[edge.source].append(edge.target)
    return adj


def _dfs_has_cycle(
    node: str,
    adj: dict[str, list[str]],
    visited: set[str],
    rec_stack: set[str],
) -> bool:
    visited.add(node)
    rec_stack.add(node)
    for neighbor in adj.get(node, []):
        if neighbor not in visited:
            if _dfs_has_cycle(neighbor, adj, visited, rec_stack):
                return True
        elif neighbor in rec_stack:
            return True
    rec_stack.discard(node)
    return False


class _WorkflowDSLSchema(BaseModel):
    nodes: list[_NodeDef]
    edges: list[_EdgeDef] = []

    @model_validator(mode="after")
    def validate_dag(self) -> _WorkflowDSLSchema:
        node_ids = {n.id for n in self.nodes}
        for edge in self.edges:
            if edge.source not in node_ids:
                raise ValueError(f"Edge source '{edge.source}' not in nodes")
            if edge.target not in node_ids:
                raise ValueError(f"Edge target '{edge.target}' not in nodes")
        adj = _build_adjacency(self.nodes, self.edges)
        visited: set[str] = set()
        rec_stack: set[str] = set()
        for node_id in node_ids:
            if node_id not in visited and _dfs_has_cycle(
                node_id, adj, visited, rec_stack
            ):
                raise ValueError(
                    "Workflow DSL contains a cycle (loops are not supported)"
                )
        return self


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    dsl: dict[str, Any] = Field(default_factory=dict)

    @field_validator("dsl", mode="before")
    @classmethod
    def validate_dsl_structure(cls, v: Any) -> Any:
        # Only validate when the DSL contains a `nodes` key so that
        # minimal / legacy payloads (e.g. `{}`) remain accepted.
        if isinstance(v, dict) and "nodes" in v:
            _WorkflowDSLSchema.model_validate(v)
        return v


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
@limiter.limit("20/minute")
async def update_workflow(
    request: Request,
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
@limiter.limit("30/minute")
async def delete_workflow(
    request: Request,
    workflow_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    workflow = await _get_workflow_or_404(db, workflow_id, user.id)
    await db.delete(workflow)
    await db.commit()
    return {"status": "ok"}
