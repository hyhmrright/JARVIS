"""Tool permission definitions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDef:
    """Metadata for a single tool available to the agent."""

    name: str
    label: str
    description: str
    default_enabled: bool


# All available tools with metadata
TOOL_REGISTRY: list[ToolDef] = [
    ToolDef(
        "datetime",
        "Date/Time",
        "Get current date and time",
        default_enabled=True,
    ),
    ToolDef(
        "code_exec",
        "Code Execution",
        "Execute Python code",
        default_enabled=True,
    ),
    ToolDef(
        "web_fetch",
        "Web Fetch",
        "Fetch web page content",
        default_enabled=True,
    ),
    ToolDef(
        "search",
        "Web Search",
        "Search the web (requires Tavily key)",
        default_enabled=True,
    ),
    ToolDef(
        "rag_search",
        "Knowledge Base",
        "Search uploaded documents",
        default_enabled=True,
    ),
    ToolDef(
        "shell",
        "Shell",
        "Execute shell commands",
        default_enabled=False,
    ),
    ToolDef(
        "browser",
        "Browser",
        "Navigate web pages with headless browser",
        default_enabled=False,
    ),
    ToolDef(
        "file",
        "File Operations",
        "Read/write/list user files",
        default_enabled=True,
    ),
    ToolDef(
        "subagent",
        "Sub-Agent",
        "Delegate subtasks to an independent sub-agent",
        default_enabled=False,
    ),
    ToolDef(
        "mcp",
        "MCP Servers",
        "Tools from connected MCP servers (configured via MCP_SERVERS_JSON)",
        default_enabled=False,
    ),
    ToolDef(
        "cron",
        "Cron Scheduler",
        "Schedule recurring tasks with cron expressions",
        default_enabled=False,
    ),
]

TOOL_NAMES: set[str] = {t.name for t in TOOL_REGISTRY}

DEFAULT_ENABLED_TOOLS: list[str] = [t.name for t in TOOL_REGISTRY if t.default_enabled]
