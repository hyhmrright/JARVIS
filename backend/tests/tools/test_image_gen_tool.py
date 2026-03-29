"""Tests for the image generation tool factory."""

import pytest
from langchain_core.tools import BaseTool

from app.tools.image_gen_tool import ImageGenTool, create_image_gen_tool


def test_create_image_gen_tool_returns_none_without_key():
    """create_image_gen_tool(None) must return None."""
    result = create_image_gen_tool(None)
    assert result is None


def test_create_image_gen_tool_returns_none_for_empty_string():
    """create_image_gen_tool('') must return None (falsy key)."""
    result = create_image_gen_tool("")
    assert result is None


def test_create_image_gen_tool_returns_tool_with_key():
    """create_image_gen_tool with a non-empty key must return a BaseTool instance."""
    tool = create_image_gen_tool("sk-test-key-123")
    assert tool is not None
    assert isinstance(tool, BaseTool)


def test_image_gen_tool_name():
    """ImageGenTool must expose the 'image_gen' tool name."""
    tool = create_image_gen_tool("sk-test-key-123")
    assert tool is not None
    assert tool.name == "image_gen"


def test_image_gen_tool_has_description():
    """ImageGenTool must have a non-empty description."""
    tool = create_image_gen_tool("sk-test-key-123")
    assert tool is not None
    assert len(tool.description) > 0


@pytest.mark.anyio
async def test_image_gen_tool_arun_returns_string_on_api_error():
    """_arun must catch API errors and return a string (not raise)."""
    from unittest.mock import AsyncMock, MagicMock, patch

    import openai

    tool = ImageGenTool(openai_api_key="sk-fake")

    mock_client = MagicMock()
    mock_client.images = MagicMock()
    mock_client.images.generate = AsyncMock(side_effect=openai.OpenAIError("API error"))

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        result = await tool._arun(prompt="a cat", size="1024x1024")

    assert isinstance(result, str)
    assert "Error" in result
