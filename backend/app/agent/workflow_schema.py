"""Workflow DSL validation schemas.

These Pydantic models validate the node/edge structure of a workflow DSL
before it is persisted or compiled. They live here — adjacent to the
GraphCompiler — so that the validation contract and the execution contract
are co-located in the agent layer rather than spread across api/.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator


class _NodeDefBase(BaseModel):
    id: str
    data: dict[str, Any] = {}


class InputNodeDef(_NodeDefBase):
    type: Literal["input"]


class LLMNodeDef(_NodeDefBase):
    type: Literal["llm"]


class ToolNodeDef(_NodeDefBase):
    type: Literal["tool"]


class ConditionNodeDef(_NodeDefBase):
    type: Literal["condition"]


class OutputNodeDef(_NodeDefBase):
    type: Literal["output"]


class ImageGenNodeDef(_NodeDefBase):
    type: Literal["image_gen"]


NodeDef = Annotated[
    InputNodeDef
    | LLMNodeDef
    | ToolNodeDef
    | ConditionNodeDef
    | OutputNodeDef
    | ImageGenNodeDef,
    Field(discriminator="type"),
]


class EdgeDef(BaseModel):
    model_config = {"populate_by_name": True}

    id: str
    source: str
    target: str
    source_handle: str | None = Field(default=None, alias="sourceHandle")
    target_handle: str | None = Field(default=None, alias="targetHandle")


def _build_adjacency(
    nodes: Sequence[_NodeDefBase], edges: list[EdgeDef]
) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {n.id: [] for n in nodes}
    for edge in edges:
        adj[edge.source].append(edge.target)
    return adj


def _dfs_has_cycle(
    start: str,
    adj: dict[str, list[str]],
    visited: set[str],
    rec_stack: set[str],
) -> bool:
    """Iterative DFS cycle detection. Avoids Python recursion limit on large graphs.

    Nodes are added to both `visited` and `rec_stack` before being pushed onto
    the stack. This prevents false positives on DAGs with shared targets (diamond
    graphs): a node reachable via two paths will be skipped on the second visit
    because it is already in `visited` but not in `rec_stack` (it was removed
    when its first traversal completed).
    """
    stack = [(start, iter(adj.get(start, [])))]
    visited.add(start)
    rec_stack.add(start)
    while stack:
        node, children = stack[-1]
        try:
            neighbor = next(children)
            if neighbor not in visited:
                visited.add(neighbor)
                rec_stack.add(neighbor)
                stack.append((neighbor, iter(adj.get(neighbor, []))))
            elif neighbor in rec_stack:
                return True
        except StopIteration:
            rec_stack.discard(node)
            stack.pop()
    return False


class WorkflowDSLSchema(BaseModel):
    """Strict validation schema for a workflow DSL dict.

    Validates node types via discriminated union and rejects cyclic graphs.
    Use app.agent.compiler.WorkflowDSL for the permissive execution schema.
    """

    nodes: list[NodeDef]
    edges: list[EdgeDef] = []

    @model_validator(mode="after")
    def validate_dag(self) -> WorkflowDSLSchema:
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
