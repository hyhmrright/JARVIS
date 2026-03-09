from pathlib import Path
from unittest.mock import patch

import pytest

from app.plugins.loader import load_markdown_skills
from app.plugins.registry import PluginRegistry


@pytest.mark.asyncio
async def test_load_markdown_skills(tmp_path: Path):
    """验证是否能从目录加载 SKILL.md 文件并注册到注册表。"""
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()

    skill_file = skill_dir / "test_skill.md"
    skill_file.write_text(
        """# Test Skill
Test description.

## Parameters

- `input`: The input string.

## Implementation

```bash
echo {{input}}
```
""",
        encoding="utf-8",
    )

    registry = PluginRegistry()

    # We need to mock SandboxManager because SkillParser uses it
    with patch("app.sandbox.manager.SandboxManager"):
        await load_markdown_skills(registry, [skill_dir])

    # Check if a plugin was registered
    entries = list(registry.iter_entries())
    assert len(entries) == 1
    plugin_id, entry = entries[0]
    assert plugin_id.startswith("skill_test_skill")
    assert entry.plugin.manifest.name == "Test Skill"

    # Now simulate activation to see if tool is registered
    # activate_all_plugins calls plugin.on_load(api)
    from app.plugins.loader import activate_all_plugins

    await activate_all_plugins(registry)

    tools = registry.get_all_tools()
    tool_names = [t.name for t in tools]
    assert "test_skill" in tool_names
