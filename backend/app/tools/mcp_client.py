"""MCP (Model Context Protocol) client — loads external server tools."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import structlog
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, create_model

logger = structlog.get_logger(__name__)


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


async def create_mcp_tools(configs: list[MCPServerConfig]) -> list[BaseTool]:
    """Connect to MCP servers and return their tools as LangChain tools.

    Returns empty list if configs is empty or all connections fail.
    """
    if not configs:
        return []

    tools: list[BaseTool] = []
    for config in configs:
        try:
            server_tools = await _load_tools_from_server(config)
            tools.extend(server_tools)
            logger.info(
                "mcp_tools_loaded",
                server=config.name,
                tool_count=len(server_tools),
            )
        except Exception:
            logger.warning(
                "mcp_server_connect_failed", server=config.name, exc_info=True
            )
    return tools


async def _load_tools_from_server(config: MCPServerConfig) -> list[BaseTool]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command=config.command,
        args=config.args,
        env=config.env,
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            # Capture tool metadata only — the session closes after this block,
            # so each tool invocation must open its own connection (see TODO below).
            return [
                _make_langchain_tool(
                    t.name,
                    getattr(t, "description", "") or t.name,
                    getattr(t, "inputSchema", None) or {},
                    config,
                )
                for t in result.tools
            ]


def _build_args_schema(input_schema: dict[str, Any]) -> type[BaseModel]:
    """Build a Pydantic model from a JSON Schema object definition.

    Produces a model with one field per declared property so that LangChain
    forwards the correct keyword arguments to the tool coroutine.  Fields not
    listed in ``required`` are optional (default ``None``).  If the schema has
    no properties at all a single ``kwargs`` catch-all field is used.
    """
    props: dict[str, Any] = input_schema.get("properties", {})
    required: set[str] = set(input_schema.get("required", []))

    field_defs: dict[str, Any] = {}
    for prop_name, _prop_schema in props.items():
        if prop_name in required:
            field_defs[prop_name] = (Any, ...)
        else:
            field_defs[prop_name] = (Any, None)

    if not field_defs:
        # No declared properties — use a single optional dict field so
        # LangChain does not treat the schema as a no-args tool.
        field_defs["kwargs"] = (dict[str, Any], {})

    return create_model("_MCPArgs", **field_defs)


def _make_langchain_tool(
    tool_name: str,
    tool_desc: str,
    input_schema: dict[str, Any],
    config: MCPServerConfig,
) -> BaseTool:
    """Wrap a single MCP tool as a LangChain StructuredTool.

    TODO: Opening a new stdio process per invocation is wasteful. A future
    optimisation should keep a persistent subprocess pool per server config.
    """
    args_schema = _build_args_schema(input_schema)

    async def _invoke(**kwargs: Any) -> str:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            server_params = StdioServerParameters(
                command=config.command,
                args=config.args,
                env=config.env,
            )
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=kwargs)
                    parts = [
                        c.text for c in result.content if hasattr(c, "text") and c.text
                    ]
                    return "\n".join(parts) or "(no output)"
        except Exception as exc:
            return f"MCP tool error ({tool_name}): {exc}"

    return StructuredTool.from_function(
        coroutine=_invoke,
        name=tool_name,
        description=tool_desc,
        args_schema=args_schema,
    )


def parse_mcp_configs(json_str: str) -> list[MCPServerConfig]:
    """Parse MCP_SERVERS_JSON env var into MCPServerConfig list.

    Returns empty list on empty string or parse errors.
    """
    if not json_str.strip():
        return []
    try:
        raw = json.loads(json_str)
        return [MCPServerConfig(**item) for item in raw]
    except (json.JSONDecodeError, TypeError, KeyError):
        logger.warning("mcp_servers_json_parse_error", json_str=json_str[:200])
        return []
