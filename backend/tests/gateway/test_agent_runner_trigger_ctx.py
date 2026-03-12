def _make_trigger_ctx() -> dict:
    return {
        "trigger_type": "semantic_watcher",
        "url": "https://example.com",
        "target": "产品价格",
        "changed_summary": "价格从 $99 降至 $49",
        "confidence": "high",
    }


def test_trigger_ctx_injected_into_task():
    """trigger_ctx is formatted and prepended to the task string."""
    from app.gateway.agent_runner import format_trigger_context

    ctx = _make_trigger_ctx()
    result = format_trigger_context(ctx)
    assert "[触发上下文]" in result
    assert "价格从 $99 降至 $49" in result
    assert "产品价格" in result


def test_run_agent_without_trigger_ctx_unchanged():
    """When trigger_ctx is None, format_trigger_context returns empty string."""
    from app.gateway.agent_runner import format_trigger_context

    result = format_trigger_context(None)
    assert result == ""
