"""Workflow execution engine.

Executes the JARVIS workflow DSL (nodes + edges) as an async generator
that yields per-node progress events.

DSL schema: { "nodes": [...], "edges": [...] }
Node types: input, output, llm, tool, condition
Variable interpolation: {{variable_name}} or {{node_id.output}}
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import structlog

# _TOOL_MAP is a module-private dict in app.agent.graph; cross-module import
# is intentional here — the workflow executor needs the same tool instances.
from app.agent.graph import _TOOL_MAP  # noqa: PLC2701
from app.db.models import UserSettings, Workflow, WorkflowRun
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)

_MAX_NODES = 50
_MAX_WALL_SECONDS = 300  # 5 minutes


def _interpolate(template: str, context: dict) -> str:
    """Replace {{key}} and {{node_id.output}} placeholders with context values."""

    def _replace(m: re.Match) -> str:
        key = m.group(1)
        parts = key.split(".", 1)
        if len(parts) == 1:
            val = context.get(parts[0])
        else:
            nested = context.get(parts[0])
            val = nested.get(parts[1], "") if isinstance(nested, dict) else ""
        return str(val) if val is not None else ""

    return re.sub(r"\{\{([\w.]+)\}\}", _replace, template)


def _topo_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Kahn's topological sort. Raises ValueError on cycle."""
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    adj: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        adj[edge["source"]].append(edge["target"])
        in_degree[edge["target"]] = in_degree.get(edge["target"], 0) + 1

    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    order: list[str] = []
    while queue:
        nid = queue.popleft()
        order.append(nid)
        for neighbor in adj[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(nodes):
        raise ValueError("Workflow contains a cycle")
    return order


def _eval_condition(left: str, operator: str, right: str) -> bool:
    """Evaluate a condition with explicit operator dispatch. No dynamic eval."""
    match operator:
        case "equals":
            return left == right
        case "contains":
            return right in left
        case "startswith":
            return left.startswith(right)
        case "endswith":
            return left.endswith(right)
        case "gt":
            try:
                return float(left) > float(right)
            except ValueError:
                return False
        case "lt":
            try:
                return float(left) < float(right)
            except ValueError:
                return False
        case _:
            logger.warning("unknown_condition_operator", operator=operator)
            return True  # non-blocking default


async def run_workflow(  # noqa: C901
    workflow: Workflow,
    input_data: dict,
    user_settings: UserSettings,
) -> AsyncGenerator[dict]:
    """Execute a workflow DSL and yield progress events.

    Yields:
        { "type": "node_done", "node_id": str, "output": str, "duration_ms": int }
        { "type": "run_done", "run_id": str, "status": "completed"|"failed" }
    """
    dsl: dict = workflow.dsl or {}
    nodes: list[dict] = dsl.get("nodes", [])
    edges: list[dict] = dsl.get("edges", [])

    if len(nodes) > _MAX_NODES:
        raise ValueError(f"Workflow exceeds maximum node count ({_MAX_NODES})")

    # Create WorkflowRun record
    run_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        async with db.begin():
            run = WorkflowRun(
                id=run_id,
                workflow_id=workflow.id,
                user_id=workflow.user_id,
                status="running",
                input_data=input_data,
            )
            db.add(run)

    node_map = {n["id"]: n for n in nodes}
    context: dict[str, Any] = {}
    run_log: list[dict] = []
    final_status = "completed"
    error_message: str | None = None

    try:
        order = _topo_sort(nodes, edges)
        async with asyncio.timeout(_MAX_WALL_SECONDS):
            for node_id in order:
                node = node_map[node_id]
                node_type = node["type"]
                data = node.get("data", {})
                t0 = time.monotonic()
                output = ""

                try:
                    if node_type == "input":
                        var = data.get("variable", node_id)
                        output = str(input_data.get(var, ""))
                        context[var] = output

                    elif node_type == "output":
                        output = _interpolate(data.get("value", ""), context)

                    elif node_type == "llm":
                        from app.agent.llm import get_llm_with_fallback

                        api_keys_raw = user_settings.api_keys or {}
                        # Decrypt keys if encrypted (same as chat.py pattern)
                        from app.core.security import decrypt_api_keys

                        raw_keys = decrypt_api_keys(api_keys_raw)
                        provider_key = raw_keys.get(user_settings.model_provider)
                        if isinstance(provider_key, list):
                            provider_key = provider_key[0] if provider_key else ""
                        provider_key = provider_key or ""

                        llm = get_llm_with_fallback(
                            provider=user_settings.model_provider,
                            model=user_settings.model_name,
                            api_key=provider_key,
                            base_url=None,
                            temperature=user_settings.temperature,
                            max_tokens=user_settings.max_tokens,
                        )
                        prompt = _interpolate(data.get("prompt", ""), context)
                        from langchain_core.messages import HumanMessage

                        response = await llm.ainvoke([HumanMessage(content=prompt)])
                        # 确保 output 为字符串
                        content = getattr(response, "content", str(response))
                        if isinstance(content, list):
                            output = str(content[0])
                        else:
                            output = str(content)

                    elif node_type == "tool":
                        tool_name = data.get("tool_name", "")
                        tool = _TOOL_MAP.get(tool_name)
                        if not tool:
                            raise ValueError(f"Unknown tool: {tool_name}")
                        params = {
                            k: _interpolate(str(v), context)
                            for k, v in data.get("params", {}).items()
                        }
                        result = (
                            await tool.arun(params)
                            if hasattr(tool, "arun")
                            else tool.run(params)
                        )
                        output = str(result)

                    elif node_type == "condition":
                        left = _interpolate(data.get("left", ""), context)
                        right = _interpolate(data.get("right", ""), context)
                        operator = data.get("operator", "equals")
                        result = _eval_condition(left, operator, right)
                        output = str(result)

                except Exception as exc:
                    output = f"[Error in node {node_id}: {exc}]"
                    logger.warning(
                        "workflow_node_error", node_id=node_id, exc_info=True
                    )

                duration_ms = int((time.monotonic() - t0) * 1000)
                context[node_id] = {"output": output}
                run_log.append(
                    {
                        "node_id": node_id,
                        "status": "done",
                        "output": output[:500],
                        "duration_ms": duration_ms,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

                yield {
                    "type": "node_done",
                    "node_id": node_id,
                    "output": output,
                    "duration_ms": duration_ms,
                }

    except TimeoutError:
        final_status = "failed"
        error_message = "Workflow exceeded 5-minute time limit"
    except asyncio.CancelledError:
        # Client disconnected — mark as failed, then re-raise so FastAPI
        # can clean up the streaming response correctly.
        final_status = "failed"
        error_message = "Cancelled"
        raise
    except ValueError as exc:
        final_status = "failed"
        error_message = str(exc)
    except Exception as exc:
        final_status = "failed"
        error_message = f"Unexpected error: {exc}"
        logger.exception("workflow_execution_error", workflow_id=str(workflow.id))

    # Persist final run state
    output_data = {nid: ctx for nid, ctx in context.items() if isinstance(ctx, dict)}
    async with AsyncSessionLocal() as db:
        async with db.begin():
            run_obj = await db.get(WorkflowRun, run_id)
            if run_obj:
                run_obj.status = final_status
                run_obj.output_data = output_data
                run_obj.error_message = error_message
                run_obj.run_log = run_log
                run_obj.completed_at = datetime.now(UTC)

    from app.core.notifications import create_notification

    body_text = (
        error_message[:100]
        if error_message
        else "Workflow execution finished successfully."
    )
    await create_notification(
        user_id=workflow.user_id,
        type=f"workflow_{final_status}",
        title=f"Workflow {final_status.capitalize()}: {workflow.name}",
        body=body_text,
        action_url="/workflows",
        metadata={"workflow_id": str(workflow.id), "run_id": str(run_id)},
        db=db,
    )

    yield {"type": "run_done", "run_id": str(run_id), "status": final_status}
