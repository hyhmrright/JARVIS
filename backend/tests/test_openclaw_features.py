import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from langchain_core.messages import HumanMessage

from app.agent.graph import create_graph
from app.agent.state import AgentState
from app.plugins.loader import _load_plugin_package
from app.plugins.registry import PluginRegistry
from app.scheduler.triggers import evaluate_trigger
from app.services.memory_sync import sync_conversation_to_markdown


@pytest.mark.asyncio
async def test_plugin_manifest_yaml_loading(tmp_path: Path):
    """验证是否能从文件夹和 manifest.yaml 加载插件并自动注册工具。"""
    plugin_dir = tmp_path / "test_skill"
    plugin_dir.mkdir()

    manifest = {
        "plugin_id": "weather_skill",
        "name": "Weather Skill",
        "description": "Checks weather",
        "version": "1.0.0",
    }
    (plugin_dir / "manifest.yaml").write_text(yaml.dump(manifest))

    code = (
        "from app.plugins.sdk import SimpleSkillPlugin\n"
        "class WeatherPlugin(SimpleSkillPlugin):\n"
        "    async def get_temp(self, city: str) -> str:\n"
        '        """Get temp doc."""\n'
        "        return f'25C in {city}'\n"
    )
    (plugin_dir / "main.py").write_text(code)

    reg = PluginRegistry()
    # Import and register
    _load_plugin_package(plugin_dir, reg)

    # Actually activate it to trigger on_load (which does auto-tooling)
    from app.plugins.loader import activate_all_plugins

    await activate_all_plugins(reg)

    tools = reg.get_all_tools()
    tool_names = [t.name for t in tools]
    assert "weather_skill_get_temp" in tool_names


@pytest.mark.asyncio
async def test_skill_md_loading(tmp_path: Path):
    """验证是否能加载根目录下的 SKILL.md 文件并转化为工具。"""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    
    skill_content = """# System Info
Get system information using uname.

## Parameters

- `options`: uname options (e.g. -a).

## Implementation

```bash
uname {{options}}
```
"""
    (skills_dir / "system_info.md").write_text(skill_content, encoding="utf-8")
    
    from app.plugins.loader import load_markdown_skills, activate_all_plugins
    from app.plugins.registry import PluginRegistry
    
    reg = PluginRegistry()
    with patch("app.sandbox.manager.SandboxManager"):
        await load_markdown_skills(reg, [skills_dir])
        await activate_all_plugins(reg)
    
    tools = reg.get_all_tools()
    tool_names = [t.name for t in tools]
    assert "system_info" in tool_names
    
    # Verify description
    si_tool = next(t for t in tools if t.name == "system_info")
    assert "Get system information" in si_tool.description


@pytest.mark.asyncio
async def test_memory_markdown_sync(tmp_path: Path):
    """验证对话是否能同步为本地 Markdown 文件。"""
    from app.core.config import settings

    settings.memory_sync_dir = str(tmp_path / "memory")
    conv_id = uuid.uuid4()

    # Patch AsyncSessionLocal INSIDE the module to intercept instantiation
    with patch("app.services.memory_sync.AsyncSessionLocal") as mock_session_factory:
        mock_db = AsyncMock()
        # Mock context manager: AsyncSessionLocal() -> __aenter__ -> mock_db
        mock_session_factory.return_value.__aenter__.return_value = mock_db

        mock_conv = MagicMock()
        mock_conv.id = conv_id
        mock_conv.title = "Test Talk"
        mock_conv.created_at = MagicMock()
        mock_conv.created_at.strftime.return_value = "2026-03-02"
        mock_conv.created_at.isoformat.return_value = "2026-03-02T12:00:00"
        mock_conv.updated_at.isoformat.return_value = "2026-03-02T12:00:00"

        mock_db.get.return_value = mock_conv

        msg1 = MagicMock()
        msg1.role = "human"
        msg1.content = "Hi"
        msg1.created_at.strftime.return_value = "12:00:00"

        mock_res = MagicMock()
        mock_res.all.return_value = [msg1]
        mock_db.scalars.return_value = mock_res

        await sync_conversation_to_markdown(conv_id)

        sync_files = list(Path(settings.memory_sync_dir).glob("*.md"))
        assert len(sync_files) == 1


@pytest.mark.asyncio
async def test_proactive_triggers():
    metadata = {"url": "https://example.com", "last_hash": "old"}
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = "new"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        fired = await evaluate_trigger("web_watcher", metadata)
        assert fired is True


@pytest.mark.asyncio
async def test_hitl_security_interruption():
    graph = create_graph(
        provider="openai", model="gpt-4o", api_key="sk-test", enabled_tools=["shell"]
    )
    from langchain_core.messages import AIMessage

    mock_llm_response = AIMessage(
        content="",
        tool_calls=[{"name": "shell", "args": {"command": "ls"}, "id": "c1"}],
    )
    with patch("langchain_openai.ChatOpenAI.ainvoke", return_value=mock_llm_response):
        state = AgentState(messages=[HumanMessage(content="ls")])
        async for chunk in graph.astream(state):
            if "approval" in chunk:
                return
        pytest.fail("No HITL")
