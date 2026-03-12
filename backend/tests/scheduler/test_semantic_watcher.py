import hashlib
from unittest.mock import AsyncMock, patch

import pytest

from app.scheduler.trigger_result import TriggerResult
from app.scheduler.triggers import SemanticAnalysisResult, SemanticWatcherProcessor


@pytest.fixture()
def processor():
    return SemanticWatcherProcessor()


@pytest.mark.asyncio
async def test_first_run_fire_on_init_false(processor):
    """First run with fire_on_init=False: initializes state, does NOT fire."""
    metadata = {
        "url": "https://example.com",
        "target": "产品价格",
        "fire_on_init": False,
    }
    with patch(
        "app.scheduler.triggers.fetch_page_content",
        new=AsyncMock(return_value="Price: $99"),
    ):
        result = await processor.should_fire(metadata)
    assert isinstance(result, TriggerResult)
    assert result.fired is False
    assert result.reason == "first_run_initialized"
    assert "content_hash" in metadata
    assert metadata["last_semantic_summary"] == "Price: $99"[:200]


@pytest.mark.asyncio
async def test_first_run_fire_on_init_true(processor):
    """First run with fire_on_init=True: fires immediately."""
    metadata = {
        "url": "https://example.com",
        "target": "产品价格",
        "fire_on_init": True,
    }
    with patch(
        "app.scheduler.triggers.fetch_page_content",
        new=AsyncMock(return_value="Price: $99"),
    ):
        result = await processor.should_fire(metadata)
    assert result.fired is True
    assert result.reason == "fired"
    assert result.trigger_ctx is not None
    assert result.trigger_ctx["changed_summary"] == "已初始化监控"


@pytest.mark.asyncio
async def test_content_hash_unchanged_skips_llm(processor):
    """If content hash matches, _analyze is NOT called."""
    content = "Price: $99"
    content_hash = hashlib.md5(content.encode()).hexdigest()
    metadata = {
        "url": "https://example.com",
        "target": "产品价格",
        "content_hash": content_hash,
        "last_semantic_summary": "价格为 $99",
    }
    with patch(
        "app.scheduler.triggers.fetch_page_content",
        new=AsyncMock(return_value=content),
    ):
        with patch.object(processor, "_analyze", new=AsyncMock()) as mock_analyze:
            result = await processor.should_fire(metadata)
    mock_analyze.assert_not_called()
    assert result.fired is False
    assert result.reason == "content_hash_unchanged"


@pytest.mark.asyncio
async def test_semantic_change_detected(processor):
    """Content changed + LLM says changed=True → fires."""
    old_content = "Price: $99"
    new_content = "Price: $49"
    old_hash = hashlib.md5(old_content.encode()).hexdigest()
    metadata = {
        "url": "https://example.com",
        "target": "产品价格",
        "content_hash": old_hash,
        "last_semantic_summary": "价格为 $99",
    }
    analysis = SemanticAnalysisResult(
        changed=True, summary="价格从 $99 降至 $49", confidence="high"
    )
    with patch(
        "app.scheduler.triggers.fetch_page_content",
        new=AsyncMock(return_value=new_content),
    ):
        with patch.object(processor, "_analyze", new=AsyncMock(return_value=analysis)):
            result = await processor.should_fire(metadata)

    assert result.fired is True
    assert result.reason == "fired"
    assert result.trigger_ctx["changed_summary"] == "价格从 $99 降至 $49"
    assert result.trigger_ctx["confidence"] == "high"
    assert metadata["last_semantic_summary"] == "价格从 $99 降至 $49"


@pytest.mark.asyncio
async def test_semantic_no_change(processor):
    """Content changed but LLM says changed=False → skips."""
    metadata = {
        "url": "https://example.com",
        "target": "产品价格",
        "content_hash": "oldhash",
        "last_semantic_summary": "价格为 $99",
    }
    analysis = SemanticAnalysisResult(
        changed=False, summary="仅格式变动", confidence="high"
    )
    with patch(
        "app.scheduler.triggers.fetch_page_content",
        new=AsyncMock(return_value="new content"),
    ):
        with patch.object(processor, "_analyze", new=AsyncMock(return_value=analysis)):
            result = await processor.should_fire(metadata)

    assert result.fired is False
    assert result.reason == "skipped"
