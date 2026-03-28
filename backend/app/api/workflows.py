from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.limiter import limiter
from app.db.models import User, Workflow, WorkflowRun
from app.db.session import AsyncSessionLocal, get_db

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
    model_config = ConfigDict(from_attributes=True)


class WorkflowPage(BaseModel):
    items: list[WorkflowOut]
    total: int


@router.get("", response_model=WorkflowPage)
async def list_workflows(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowPage:
    total = (
        await db.scalar(
            select(func.count(Workflow.id)).where(Workflow.user_id == user.id)
        )
    ) or 0
    rows = await db.scalars(
        select(Workflow)
        .where(Workflow.user_id == user.id)
        .order_by(Workflow.name)
        .limit(limit)
        .offset(offset)
    )
    return WorkflowPage(
        items=[WorkflowOut.model_validate(w) for w in rows.all()], total=total
    )


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


# ---------------------------------------------------------------------------
# Workflow runs
# ---------------------------------------------------------------------------


class WorkflowRunOut(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunOut])
async def list_workflow_runs(
    workflow_id: uuid.UUID,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List workflow run history (newest first)."""
    wf_result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id, Workflow.user_id == current_user.id
        )
    )
    if wf_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    result = await db.execute(
        select(WorkflowRun)
        .where(
            WorkflowRun.workflow_id == workflow_id,
            WorkflowRun.user_id == current_user.id,
        )
        .order_by(WorkflowRun.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Workflow execution (SSE)
# ---------------------------------------------------------------------------


class WorkflowExecuteRequest(BaseModel):
    inputs: dict[str, Any] = {}


def _llm_config_from_settings(user_settings: Any) -> dict[str, Any]:
    """Build llm_config dict from user settings, decrypting the API key."""
    provider = "deepseek"
    model = "deepseek-chat"
    api_key = ""
    if user_settings:
        provider = user_settings.model_provider or "deepseek"
        model = user_settings.model_name or "deepseek-chat"
        try:
            from app.core.security import fernet_decrypt

            raw_key = (user_settings.api_keys or {}).get(provider, "")
            api_key = fernet_decrypt(raw_key) if raw_key else ""
        except Exception:
            logger.warning("workflow_api_key_decrypt_failed", exc_info=True)
            api_key = ""
    return {"provider": provider, "model": model, "api_key": api_key}


async def _update_run_status(
    run_uuid: uuid.UUID,
    status: str,
    *,
    completed_at: datetime | None = None,
    error_message: str | None = None,
) -> None:
    """Persist run status to DB in a fresh session."""
    async with AsyncSessionLocal() as update_db:
        run_record = await update_db.get(WorkflowRun, run_uuid)
        if run_record:
            run_record.status = status
            if completed_at is not None:
                run_record.completed_at = completed_at
            if error_message is not None:
                run_record.error_message = error_message
            await update_db.commit()


@router.post("/{workflow_id}/execute")
@limiter.limit("10/minute")
async def execute_workflow(
    request: Request,
    workflow_id: uuid.UUID,
    body: WorkflowExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Execute a workflow and stream node events via SSE."""
    import json as _json

    wf_result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id, Workflow.user_id == current_user.id
        )
    )
    workflow = wf_result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    from app.db.models import UserSettings

    settings_result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    user_settings = settings_result.scalar_one_or_none()

    # Create run record
    run = WorkflowRun(
        workflow_id=workflow.id,
        user_id=current_user.id,
        status="running",
        input_data=body.inputs,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    run_id = str(run.id)
    run_uuid = run.id
    dsl = workflow.dsl
    llm_config = _llm_config_from_settings(user_settings)

    async def event_stream() -> Any:
        try:
            from langchain_core.messages import HumanMessage

            from app.agent.compiler import GraphCompiler, WorkflowDSL

            compiler = GraphCompiler(
                dsl=WorkflowDSL.model_validate(dsl),
                llm_config=llm_config,
            )
            graph = compiler.compile()

            state = {
                "messages": [HumanMessage(content=_json.dumps(body.inputs))],
                "node_outputs": {},
            }

            seen_outputs: set[str] = set()
            async for chunk in graph.astream(state):
                node_outputs = chunk.get("node_outputs") or {}
                for node_id, output in node_outputs.items():
                    if node_id not in seen_outputs:
                        seen_outputs.add(node_id)
                        event = {
                            "type": "node_done",
                            "node_id": node_id,
                            "output": str(output),
                            "duration_ms": 0,
                        }
                        yield f"data: {_json.dumps(event)}\n\n"

            await _update_run_status(
                run_uuid, "completed", completed_at=datetime.now(UTC)
            )
            done_event = {"type": "run_done", "run_id": run_id, "status": "completed"}
            yield f"data: {_json.dumps(done_event)}\n\n"

        except Exception as exc:
            logger.exception("workflow_stream_error", run_id=run_id)
            err_event = {"type": "run_error", "run_id": run_id, "error": str(exc)}
            yield f"data: {_json.dumps(err_event)}\n\n"
            await _update_run_status(run_uuid, "failed", error_message=str(exc))

    return StreamingResponse(event_stream(), media_type="text/event-stream")
