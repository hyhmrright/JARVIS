"""Tests for WorkflowDSLSchema validation."""

import pytest
from pydantic import ValidationError

from app.agent.workflow_schema import (
    EdgeDef,
    WorkflowDSLSchema,
)

# ---------------------------------------------------------------------------
# Valid DSL
# ---------------------------------------------------------------------------


def test_valid_dsl_minimal():
    """A DSL with only nodes and no edges is valid."""
    dsl = WorkflowDSLSchema(
        nodes=[
            {"id": "n1", "type": "input"},
            {"id": "n2", "type": "output"},
        ],
        edges=[],
    )
    assert len(dsl.nodes) == 2


def test_valid_dsl_with_edges():
    """A linear DAG (input → llm → output) should pass validation."""
    dsl = WorkflowDSLSchema(
        nodes=[
            {"id": "start", "type": "input"},
            {"id": "llm1", "type": "llm"},
            {"id": "end", "type": "output"},
        ],
        edges=[
            {"id": "e1", "source": "start", "target": "llm1"},
            {"id": "e2", "source": "llm1", "target": "end"},
        ],
    )
    assert len(dsl.edges) == 2


def test_all_node_types_accepted():
    """All supported node type literals should be accepted."""
    for node_type in ("input", "llm", "tool", "condition", "output", "image_gen"):
        dsl = WorkflowDSLSchema(nodes=[{"id": "n", "type": node_type}], edges=[])
        assert dsl.nodes[0].type == node_type


# ---------------------------------------------------------------------------
# Missing / invalid fields
# ---------------------------------------------------------------------------


def test_missing_node_id_fails():
    """A node without an 'id' must fail validation."""
    with pytest.raises(ValidationError):
        WorkflowDSLSchema(nodes=[{"type": "input"}], edges=[])


def test_unknown_node_type_fails():
    """An unrecognised node type must fail the discriminated-union check."""
    with pytest.raises(ValidationError):
        WorkflowDSLSchema(nodes=[{"id": "n1", "type": "unknown_type"}], edges=[])


# ---------------------------------------------------------------------------
# Edge reference validation
# ---------------------------------------------------------------------------


def test_edge_unknown_source_fails():
    """An edge whose source is not in the node list must be rejected."""
    with pytest.raises(ValidationError, match="source"):
        WorkflowDSLSchema(
            nodes=[{"id": "n1", "type": "input"}],
            edges=[{"id": "e1", "source": "ghost", "target": "n1"}],
        )


def test_edge_unknown_target_fails():
    """An edge whose target is not in the node list must be rejected."""
    with pytest.raises(ValidationError, match="target"):
        WorkflowDSLSchema(
            nodes=[{"id": "n1", "type": "input"}],
            edges=[{"id": "e1", "source": "n1", "target": "ghost"}],
        )


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def test_cycle_two_nodes_fails():
    """A direct cycle between two nodes must be rejected."""
    with pytest.raises(ValidationError, match="cycle"):
        WorkflowDSLSchema(
            nodes=[
                {"id": "a", "type": "llm"},
                {"id": "b", "type": "llm"},
            ],
            edges=[
                {"id": "e1", "source": "a", "target": "b"},
                {"id": "e2", "source": "b", "target": "a"},
            ],
        )


def test_cycle_three_nodes_fails():
    """A cycle spanning three nodes must be detected."""
    with pytest.raises(ValidationError, match="cycle"):
        WorkflowDSLSchema(
            nodes=[
                {"id": "a", "type": "llm"},
                {"id": "b", "type": "tool"},
                {"id": "c", "type": "condition"},
            ],
            edges=[
                {"id": "e1", "source": "a", "target": "b"},
                {"id": "e2", "source": "b", "target": "c"},
                {"id": "e3", "source": "c", "target": "a"},
            ],
        )


def test_diamond_dag_is_valid():
    """A diamond-shaped DAG (two paths converging) must NOT be rejected as a cycle."""
    dsl = WorkflowDSLSchema(
        nodes=[
            {"id": "top", "type": "input"},
            {"id": "left", "type": "llm"},
            {"id": "right", "type": "tool"},
            {"id": "bottom", "type": "output"},
        ],
        edges=[
            {"id": "e1", "source": "top", "target": "left"},
            {"id": "e2", "source": "top", "target": "right"},
            {"id": "e3", "source": "left", "target": "bottom"},
            {"id": "e4", "source": "right", "target": "bottom"},
        ],
    )
    assert len(dsl.nodes) == 4


# ---------------------------------------------------------------------------
# EdgeDef alias / sourceHandle / targetHandle
# ---------------------------------------------------------------------------


def test_edge_def_source_handle_alias():
    """EdgeDef should accept camelCase 'sourceHandle' alias."""
    edge = EdgeDef.model_validate(
        {"id": "e1", "source": "a", "target": "b", "sourceHandle": "out"}
    )
    assert edge.source_handle == "out"


def test_edge_def_target_handle_alias():
    """EdgeDef should accept camelCase 'targetHandle' alias."""
    edge = EdgeDef.model_validate(
        {"id": "e1", "source": "a", "target": "b", "targetHandle": "in"}
    )
    assert edge.target_handle == "in"
