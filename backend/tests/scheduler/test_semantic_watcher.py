from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scheduler.triggers import evaluate_trigger


@pytest.mark.asyncio
async def test_semantic_watcher_trigger_no_change():
    """验证当网页内容变动但语义一致时，不触发任务。"""
    # 假设网页内容变了，但内容主旨没变
    metadata = {
        "url": "https://example.com",
        "last_semantic_summary": "这是一篇关于 AI 的新闻摘要。",
        "target": "主旨"
    }

    # 模拟抓取到的网页内容
    new_content = "<html><body>这是一篇关于人工智能（AI）的最新资讯摘要。</body></html>"

    with (
        patch("httpx.AsyncClient.get") as mock_get,
        patch("app.scheduler.triggers.get_llm_with_fallback") as mock_get_llm
    ):
        # 模拟 HTTP 响应
        mock_resp = AsyncMock()
        mock_resp.text = new_content
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value.__aenter__.return_value = mock_resp

        # 模拟 LLM 对比结果：语义一致
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value.content = "语义一致"
        mock_get_llm.return_value = mock_llm

        # 即使 trigger_type="semantic_watcher" 尚未注册，
        # 我们也期望它目前失败或不按预期工作
        fired = await evaluate_trigger("semantic_watcher", metadata)
        assert fired is False

@pytest.mark.asyncio
async def test_semantic_watcher_trigger_significant_change():
    """验证当语义发生重大变动时，触发任务。"""
    metadata = {
        "url": "https://example.com",
        "last_semantic_summary": "原价 $99。",
        "target": "价格"
    }

    # 模拟抓取到的网页内容（价格变了）
    new_content = "<html><body>现价 $49。</body></html>"

    with (
        patch("httpx.AsyncClient.get") as mock_get,
        patch("app.scheduler.triggers.get_llm_with_fallback") as mock_get_llm
    ):
        mock_resp = AsyncMock()
        mock_resp.text = new_content
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value.__aenter__.return_value = mock_resp

        # 模拟 LLM 对比结果：语义变动
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value.content = "语义已变动：价格从 $99 降至 $49。"
        mock_get_llm.return_value = mock_llm

        fired = await evaluate_trigger("semantic_watcher", metadata)
        assert fired is True
        assert "价格从 $99 降至 $49" in metadata["last_semantic_summary"]
