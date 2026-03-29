"""Tests for persona system prompt assembly."""

from unittest.mock import patch

from app.agent.persona import build_system_prompt, format_memories_for_prompt

# ---------------------------------------------------------------------------
# build_system_prompt
# ---------------------------------------------------------------------------


def test_build_system_prompt_with_override():
    """Custom persona override text must appear in the system prompt."""
    with (
        patch("app.agent.persona.load_skills", return_value=[]),
        patch("app.agent.persona.format_skills_for_prompt", return_value=""),
    ):
        result = build_system_prompt("You are a pirate assistant.")
    assert "pirate" in result.lower()


def test_build_system_prompt_without_override_returns_default():
    """No override must return a non-empty default system prompt."""
    with (
        patch("app.agent.persona.load_skills", return_value=[]),
        patch("app.agent.persona.format_skills_for_prompt", return_value=""),
    ):
        result = build_system_prompt(None)
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_system_prompt_with_empty_override():
    """Empty string override treats as falsy — default persona used."""
    with (
        patch("app.agent.persona.load_skills", return_value=[]),
        patch("app.agent.persona.format_skills_for_prompt", return_value=""),
    ):
        result = build_system_prompt("")
    assert isinstance(result, str)
    # Empty string is falsy so no custom section is injected; JARVIS persona remains
    assert "JARVIS" in result


def test_build_system_prompt_override_is_present_in_result():
    """Custom override must be present in the resulting prompt."""
    custom = "CUSTOM_MARKER_UNIQUE_STRING"
    with (
        patch("app.agent.persona.load_skills", return_value=[]),
        patch("app.agent.persona.format_skills_for_prompt", return_value=""),
    ):
        result = build_system_prompt(custom)
    assert custom in result


def test_build_system_prompt_contains_jarvis_identity():
    """Default prompt must reference JARVIS identity."""
    with (
        patch("app.agent.persona.load_skills", return_value=[]),
        patch("app.agent.persona.format_skills_for_prompt", return_value=""),
    ):
        result = build_system_prompt(None)
    assert "JARVIS" in result


# ---------------------------------------------------------------------------
# format_memories_for_prompt
# ---------------------------------------------------------------------------


def test_format_memories_empty_list_returns_empty_string():
    """Empty memory list should return an empty string."""
    result = format_memories_for_prompt([])
    assert result == ""


def test_format_memories_with_entries():
    """Memory entries should be rendered with key/value/category."""
    from unittest.mock import MagicMock

    mem = MagicMock()
    mem.category = "preference"
    mem.key = "language"
    mem.value = "Python"

    result = format_memories_for_prompt([mem])
    assert "preference" in result
    assert "language" in result
    assert "Python" in result


def test_format_memories_multiple_entries():
    """Multiple memories should all appear in the output."""
    from unittest.mock import MagicMock

    memories = []
    for i in range(3):
        m = MagicMock()
        m.category = f"cat{i}"
        m.key = f"key{i}"
        m.value = f"val{i}"
        memories.append(m)

    result = format_memories_for_prompt(memories)
    for i in range(3):
        assert f"key{i}" in result
        assert f"val{i}" in result
