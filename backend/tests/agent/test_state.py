"""Tests for AgentState initialization and field defaults."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.state import AgentState


def test_agent_state_with_messages():
    """AgentState created with a message list should store them."""
    state = AgentState(messages=[HumanMessage(content="hi")])
    assert len(state.messages) == 1
    assert state.messages[0].content == "hi"


def test_agent_state_empty_messages():
    """AgentState with no messages should default to an empty list."""
    state = AgentState(messages=[])
    assert state.messages == []


def test_agent_state_default_depth_is_zero():
    """depth field must default to 0."""
    state = AgentState(messages=[])
    assert state.depth == 0


def test_agent_state_custom_depth():
    """depth field must accept custom values."""
    state = AgentState(messages=[], depth=3)
    assert state.depth == 3


def test_agent_state_pending_tool_call_defaults_none():
    """pending_tool_call must default to None."""
    state = AgentState(messages=[])
    assert state.pending_tool_call is None


def test_agent_state_approved_defaults_none():
    """approved must default to None."""
    state = AgentState(messages=[])
    assert state.approved is None


def test_agent_state_multiple_message_types():
    """AgentState should accept mixed message types."""
    msgs = [
        SystemMessage(content="sys"),
        HumanMessage(content="human"),
        AIMessage(content="ai"),
    ]
    state = AgentState(messages=msgs)
    assert len(state.messages) == 3


def test_agent_state_pending_tool_call_set():
    """pending_tool_call field should accept a dict value."""
    call = {"name": "search", "args": {"query": "test"}}
    state = AgentState(messages=[], pending_tool_call=call)
    assert state.pending_tool_call == call


def test_agent_state_approved_set_true():
    """approved field should accept True."""
    state = AgentState(messages=[], approved=True)
    assert state.approved is True


def test_agent_state_approved_set_false():
    """approved field should accept False."""
    state = AgentState(messages=[], approved=False)
    assert state.approved is False
