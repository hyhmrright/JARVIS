from unittest.mock import AsyncMock

import pytest

from app.plugins.skill_parser import SkillParser


@pytest.fixture
def skill_md():
    return """# Get User Info
Extract information about a user from the database.

## Parameters

- `user_id`: The ID of the user to fetch.
- `format`: Output format (json or text).

## Implementation

```bash
echo "Fetching user {{user_id}} in {{format}} format..."
```
"""

@pytest.mark.asyncio
async def test_parse_markdown(skill_md):
    parser = SkillParser()
    data = parser.parse_markdown(skill_md, "test.md")

    assert data["name"] == "Get User Info"
    assert "Extract information about a user" in data["description"]
    assert data["parameters"]["user_id"] == "The ID of the user to fetch."
    assert data["parameters"]["format"] == "Output format (json or text)."
    assert data["implementation_type"] == "bash"
    assert 'echo "Fetching user {{user_id}}' in data["implementation_code"]

@pytest.mark.asyncio
async def test_create_tool(skill_md):
    parser = SkillParser()
    data = parser.parse_markdown(skill_md, "test.md")
    tool = parser.create_tool(data)

    assert tool.name == "get_user_info"
    assert "Extract information about a user" in tool.description

    # Check args schema
    schema = tool.args_schema.model_json_schema()
    assert "user_id" in schema["properties"]
    assert "format" in schema["properties"]

@pytest.mark.asyncio
async def test_execute_bash_skill():
    mock_manager = AsyncMock()
    parser = SkillParser(sandbox_manager=mock_manager)

    mock_manager.create_sandbox.return_value = "container_123"
    mock_manager.exec_in_sandbox.return_value = "Fetching user 42 in json format..."

    impl_code = 'echo "Fetching user {{user_id}} in {{format}} format..."'
    output = await parser._execute_bash(impl_code, user_id="42", format="json")

    assert "user 42" in output
    mock_manager.create_sandbox.assert_called_once()
    mock_manager.exec_in_sandbox.assert_called_once_with(
        "container_123",
        'echo "Fetching user 42 in json format..."'
    )
    mock_manager.destroy_sandbox.assert_called_once_with("container_123")

@pytest.mark.asyncio
async def test_execute_python_skill():
    mock_manager = AsyncMock()
    parser = SkillParser(sandbox_manager=mock_manager)

    mock_manager.create_sandbox.return_value = "container_123"
    mock_manager.exec_in_sandbox.return_value = "Result from python: 42"

    impl_code = "print(f'Result from python: {{user_id}}')"
    output = await parser._execute_python(impl_code, user_id="42")

    assert "Result from python: 42" in output
    # Verify setup_cmd and execution
    assert mock_manager.exec_in_sandbox.call_count == 2
    setup_call = mock_manager.exec_in_sandbox.call_args_list[0]
    assert "printf" in setup_call.args[1]
    assert "print(f" in setup_call.args[1]
    assert "Result from python: 42" in setup_call.args[1]

    exec_call = mock_manager.exec_in_sandbox.call_args_list[1]
    assert "python3 /tmp/skill.py" == exec_call.args[1]
