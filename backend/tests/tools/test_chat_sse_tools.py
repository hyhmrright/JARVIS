"""Tests for agent event generation from LangGraph chunks."""

from langchain_core.messages import AIMessage, ToolMessage

from app.agent.interpreter import events_from_chunk


def _make_llm_chunk_with_tool_calls() -> dict:
    """Create a chunk that simulates LLM deciding to call a tool."""
    ai_msg = AIMessage(content="")
    ai_msg.tool_calls = [
        {"name": "web_search", "args": {"query": "test"}, "id": "call_1"}
    ]
    return {"llm": {"messages": [ai_msg]}}


def _make_tool_result_chunk() -> dict:
    """Create a chunk that simulates tool execution result."""
    tool_msg = ToolMessage(
        content="Search result: found 3 items",
        name="web_search",
        tool_call_id="call_1",
    )
    return {"tools": {"messages": [tool_msg]}}


def _make_llm_response_chunk() -> dict:
    """Create a chunk that simulates final LLM response with text."""
    ai_msg = AIMessage(content="Based on the search results...")
    ai_msg.tool_calls = []
    return {"llm": {"messages": [ai_msg]}}


class TestAgentEvents:
    """Tests for standardized agent event generation."""

    def test_tool_start_event_emitted(self) -> None:
        """When LLM chunk has tool_calls, a tool_start event is emitted."""
        chunk = _make_llm_chunk_with_tool_calls()
        events, _ = events_from_chunk(chunk, "")

        assert len(events) == 1
        assert events[0].type == "tool_start"
        assert events[0].tool == "web_search"
        assert events[0].args == {"query": "test"}

    def test_tool_end_event_emitted(self) -> None:
        """When tools chunk appears, a tool_end event is emitted."""
        chunk = _make_tool_result_chunk()
        events, _ = events_from_chunk(chunk, "")

        assert len(events) == 1
        assert events[0].type == "tool_end"
        assert events[0].tool == "web_search"
        assert events[0].result_preview == "Search result: found 3 items"

    def test_delta_event_includes_type(self) -> None:
        """Delta events include type: 'delta'."""
        chunk = _make_llm_response_chunk()
        events, full = events_from_chunk(chunk, "")

        assert len(events) == 1
        assert events[0].type == "delta"
        assert events[0].delta == "Based on the search results..."
        assert full == "Based on the search results..."

    def test_no_event_for_empty_delta(self) -> None:
        """No delta event is emitted when content hasn't changed."""
        chunk = _make_llm_response_chunk()
        events, _ = events_from_chunk(chunk, "Based on the search results...")

        assert len(events) == 0

    def test_full_tool_call_sequence(self) -> None:
        """Full sequence: tool_start -> tool_end -> delta."""
        all_events: list = []
        full_content = ""

        # Step 1: LLM decides to call a tool
        events, full_content = events_from_chunk(
            _make_llm_chunk_with_tool_calls(), full_content
        )
        all_events.extend(events)

        # Step 2: Tool returns result
        events, full_content = events_from_chunk(
            _make_tool_result_chunk(), full_content
        )
        all_events.extend(events)

        # Step 3: LLM responds with text
        events, full_content = events_from_chunk(
            _make_llm_response_chunk(), full_content
        )
        all_events.extend(events)

        assert len(all_events) == 3
        assert all_events[0].type == "tool_start"
        assert all_events[1].type == "tool_end"
        assert all_events[2].type == "delta"

    def test_tool_end_result_preview_truncated(self) -> None:
        """Tool end result_preview is truncated to 200 chars."""
        long_content = "x" * 300
        tool_msg = ToolMessage(
            content=long_content, name="web_search", tool_call_id="call_1"
        )
        chunk = {"tools": {"messages": [tool_msg]}}
        events, _ = events_from_chunk(chunk, "")

        assert len(events[0].result_preview) == 200

    def test_multiple_tool_calls_emit_multiple_starts(self) -> None:
        """Multiple tool_calls in one LLM message emit multiple tool_start events."""
        ai_msg = AIMessage(content="")
        ai_msg.tool_calls = [
            {"name": "web_search", "args": {"query": "a"}, "id": "call_1"},
            {"name": "rag_search", "args": {"query": "b"}, "id": "call_2"},
        ]
        chunk = {"llm": {"messages": [ai_msg]}}
        events, _ = events_from_chunk(chunk, "")

        assert len(events) == 2
        assert events[0].tool == "web_search"
        assert events[1].tool == "rag_search"

    def test_llm_chunk_with_tool_calls_and_content(self) -> None:
        """LLM chunk with both tool_calls and content emits both events."""
        ai_msg = AIMessage(content="Let me search for that.")
        ai_msg.tool_calls = [
            {"name": "web_search", "args": {"query": "test"}, "id": "call_1"}
        ]
        chunk = {"llm": {"messages": [ai_msg]}}
        events, full = events_from_chunk(chunk, "")

        assert len(events) == 2
        assert events[0].type == "tool_start"
        assert events[1].type == "delta"
        assert full == "Let me search for that."
