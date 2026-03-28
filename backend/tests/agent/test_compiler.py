"""Tests for GraphCompiler and WorkflowDSLSchema.

Covers the Coverage Illusion gap identified in the Brooks-Lint Mode 4 audit:
GraphCompiler (271 lines) and WorkflowDSLSchema had zero direct tests.
"""

import pytest
from langgraph.graph.state import CompiledStateGraph
from pydantic import ValidationError

from app.agent.compiler import GraphCompiler, WorkflowDSL, WorkflowNodeDSL
from app.agent.workflow_schema import EdgeDef, WorkflowDSLSchema


def _make_edge(
    id: str, source: str, target: str, *, source_handle: str | None = None
) -> EdgeDef:
    return EdgeDef(id=id, source=source, target=target, sourceHandle=source_handle)


def _compiler(dsl: WorkflowDSL) -> GraphCompiler:
    return GraphCompiler(
        dsl=dsl, llm_config={"provider": "deepseek", "api_key": "test"}
    )


# ---------------------------------------------------------------------------
# GraphCompiler.compile() — node type dispatch
# ---------------------------------------------------------------------------


def test_compile_linear_dsl_returns_compiled_graph():
    """compile() on a 3-node linear DSL returns a CompiledStateGraph."""
    dsl = WorkflowDSL(
        nodes=[
            WorkflowNodeDSL(id="n_in", type="input", data={}),
            WorkflowNodeDSL(id="n_llm", type="llm", data={"prompt": "say hi"}),
            WorkflowNodeDSL(id="n_out", type="output", data={}),
        ],
        edges=[
            _make_edge("e1", "n_in", "n_llm"),
            _make_edge("e2", "n_llm", "n_out"),
        ],
    )
    graph = _compiler(dsl).compile()
    assert isinstance(graph, CompiledStateGraph)


def test_compile_tool_node_missing_tool_name_does_not_raise():
    """tool nodes compile without error; missing tool yields error string at runtime."""
    dsl = WorkflowDSL(
        nodes=[
            WorkflowNodeDSL(id="n_in", type="input", data={}),
            WorkflowNodeDSL(id="n_tool", type="tool", data={"tool_name": "noop"}),
            WorkflowNodeDSL(id="n_out", type="output", data={}),
        ],
        edges=[
            _make_edge("e1", "n_in", "n_tool"),
            _make_edge("e2", "n_tool", "n_out"),
        ],
    )
    graph = _compiler(dsl).compile()
    assert isinstance(graph, CompiledStateGraph)


def test_compile_condition_node_is_not_added_as_graph_node():
    """condition nodes become routers, not graph nodes — n_cond absent from graph."""
    dsl = WorkflowDSL(
        nodes=[
            WorkflowNodeDSL(id="n_in", type="input", data={}),
            WorkflowNodeDSL(
                id="n_cond",
                type="condition",
                data={"condition_expression": "{{ true }}"},
            ),
            WorkflowNodeDSL(id="n_true", type="output", data={}),
            WorkflowNodeDSL(id="n_false", type="output", data={}),
        ],
        edges=[
            _make_edge("e1", "n_in", "n_cond"),
            _make_edge("e2", "n_cond", "n_true", source_handle="true"),
            _make_edge("e3", "n_cond", "n_false", source_handle="false"),
        ],
    )
    graph = _compiler(dsl).compile()
    assert isinstance(graph, CompiledStateGraph)
    # condition node must be a router, not a registered node
    assert "n_cond" not in graph.nodes


def test_compile_entry_edge_falls_back_to_first_node_when_no_input_node():
    """When no input node exists, START connects to the first node in the list."""
    dsl = WorkflowDSL(
        nodes=[
            WorkflowNodeDSL(id="n_llm", type="llm", data={"prompt": "hello"}),
            WorkflowNodeDSL(id="n_out", type="output", data={}),
        ],
        edges=[_make_edge("e1", "n_llm", "n_out")],
    )
    graph = _compiler(dsl).compile()
    assert isinstance(graph, CompiledStateGraph)


# ---------------------------------------------------------------------------
# WorkflowDSLSchema — DAG validation
# ---------------------------------------------------------------------------


def test_validate_dag_rejects_cycle():
    """A two-node cycle must raise ValidationError mentioning 'cycle'."""
    with pytest.raises(ValidationError, match="cycle"):
        WorkflowDSLSchema.model_validate(
            {
                "nodes": [
                    {"id": "a", "type": "llm", "data": {}},
                    {"id": "b", "type": "llm", "data": {}},
                ],
                "edges": [
                    {"id": "e1", "source": "a", "target": "b"},
                    {"id": "e2", "source": "b", "target": "a"},
                ],
            }
        )


def test_validate_dag_rejects_unknown_edge_source():
    """An edge whose source is not in nodes must raise ValidationError."""
    with pytest.raises(ValidationError, match="not in nodes"):
        WorkflowDSLSchema.model_validate(
            {
                "nodes": [{"id": "a", "type": "input", "data": {}}],
                "edges": [{"id": "e1", "source": "ghost", "target": "a"}],
            }
        )


def test_validate_dag_rejects_unknown_edge_target():
    """An edge whose target is not in nodes must raise ValidationError."""
    with pytest.raises(ValidationError, match="not in nodes"):
        WorkflowDSLSchema.model_validate(
            {
                "nodes": [{"id": "a", "type": "input", "data": {}}],
                "edges": [{"id": "e1", "source": "a", "target": "ghost"}],
            }
        )


def test_validate_dag_accepts_diamond():
    """Diamond graph (root→left→sink and root→right→sink) is a valid DAG."""
    # Must not raise — iterative DFS should not false-positive on shared targets.
    WorkflowDSLSchema.model_validate(
        {
            "nodes": [
                {"id": "root", "type": "input", "data": {}},
                {"id": "left", "type": "llm", "data": {}},
                {"id": "right", "type": "llm", "data": {}},
                {"id": "sink", "type": "output", "data": {}},
            ],
            "edges": [
                {"id": "e1", "source": "root", "target": "left"},
                {"id": "e2", "source": "root", "target": "right"},
                {"id": "e3", "source": "left", "target": "sink"},
                {"id": "e4", "source": "right", "target": "sink"},
            ],
        }
    )


def test_validate_dag_rejects_unknown_node_type():
    """Discriminated union must reject nodes with an unrecognised type."""
    with pytest.raises(ValidationError):
        WorkflowDSLSchema.model_validate(
            {
                "nodes": [{"id": "n1", "type": "unknown_type", "data": {}}],
                "edges": [],
            }
        )
