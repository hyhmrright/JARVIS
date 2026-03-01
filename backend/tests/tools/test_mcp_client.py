"""Tests for MCP server client tool integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.tools.mcp_client import MCPServerConfig, parse_mcp_configs


async def test_create_mcp_tools_empty_configs():
    from app.tools.mcp_client import create_mcp_tools

    tools = await create_mcp_tools([])
    assert tools == []


async def test_parse_mcp_configs_empty_string():
    configs = parse_mcp_configs("")
    assert configs == []


async def test_parse_mcp_configs_whitespace():
    configs = parse_mcp_configs("   ")
    assert configs == []


async def test_parse_mcp_configs_invalid_json():
    configs = parse_mcp_configs("{not valid json")
    assert configs == []


async def test_parse_mcp_configs_valid():
    json_str = (
        '[{"name": "filesystem", "command": "npx",'
        ' "args": ["-y", "@modelcontextprotocol/server-filesystem"]}]'
    )
    configs = parse_mcp_configs(json_str)
    assert len(configs) == 1
    assert configs[0].name == "filesystem"
    assert configs[0].command == "npx"
    assert configs[0].args == ["-y", "@modelcontextprotocol/server-filesystem"]


async def test_parse_mcp_configs_multiple():
    json_str = (
        '[{"name": "a", "command": "cmd1", "args": []},'
        ' {"name": "b", "command": "cmd2", "args": ["--flag"]}]'
    )
    configs = parse_mcp_configs(json_str)
    assert len(configs) == 2
    assert configs[0].name == "a"
    assert configs[1].name == "b"


async def test_create_mcp_tools_connection_failure_returns_empty():
    """Connection failures should be caught and logged, not raised."""
    from app.tools.mcp_client import create_mcp_tools

    config = MCPServerConfig(name="bad-server", command="nonexistent-cmd", args=[])
    with patch(
        "app.tools.mcp_client._load_tools_from_server",
        side_effect=RuntimeError("connection refused"),
    ):
        tools = await create_mcp_tools([config])
    assert tools == []


async def test_mcp_tool_invocation():
    """Test that a wrapped MCP tool correctly calls the underlying session."""
    from app.tools.mcp_client import _make_langchain_tool

    config = MCPServerConfig(name="test-server", command="npx", args=["server"])
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    mock_result = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "file contents here"
    mock_result.content = [mock_content]

    mock_session = AsyncMock()
    mock_session.call_tool.return_value = mock_result

    mock_stdio_cm = AsyncMock()
    mock_stdio_cm.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
    mock_stdio_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client_session_cm = AsyncMock()
    mock_client_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client_session_cm.__aexit__ = AsyncMock(return_value=False)

    lc_tool = _make_langchain_tool(
        "read_file", "Read a file from the filesystem", input_schema, config
    )
    assert lc_tool.name == "read_file"
    assert "Read a file" in lc_tool.description

    with (
        patch("mcp.client.stdio.stdio_client", return_value=mock_stdio_cm),
        patch("mcp.ClientSession", return_value=mock_client_session_cm),
    ):
        result = await lc_tool.ainvoke({"path": "/tmp/test.txt"})

    assert result == "file contents here"
    mock_session.call_tool.assert_called_once_with(
        "read_file", arguments={"path": "/tmp/test.txt"}
    )


async def test_mcp_tool_invocation_error_returns_message():
    """Tool invocation errors should return a descriptive string, not raise."""
    from app.tools.mcp_client import _make_langchain_tool

    config = MCPServerConfig(name="test-server", command="npx", args=[])
    input_schema: dict = {}

    mock_stdio_cm = AsyncMock()
    mock_stdio_cm.__aenter__ = AsyncMock(side_effect=RuntimeError("process died"))
    mock_stdio_cm.__aexit__ = AsyncMock(return_value=False)

    lc_tool = _make_langchain_tool(
        "crash_tool", "A tool that crashes", input_schema, config
    )

    with patch("mcp.client.stdio.stdio_client", return_value=mock_stdio_cm):
        result = await lc_tool.ainvoke({})

    assert "MCP tool error" in result
    assert "crash_tool" in result


async def test_build_args_schema_required_fields():
    """Schema with required fields produces a model with required fields."""
    from app.tools.mcp_client import _build_args_schema

    schema = _build_args_schema(
        {
            "type": "object",
            "properties": {"path": {"type": "string"}, "mode": {"type": "string"}},
            "required": ["path"],
        }
    )
    fields = schema.model_fields
    assert "path" in fields
    assert "mode" in fields
    assert fields["path"].is_required()
    assert not fields["mode"].is_required()


async def test_build_args_schema_no_properties():
    """Schema with no properties produces a model with a kwargs catch-all field."""
    from app.tools.mcp_client import _build_args_schema

    schema = _build_args_schema({})
    assert "kwargs" in schema.model_fields
