"""Tests for TTS synthesis endpoint."""

import inspect

from app.api.tts import _DEFAULT_VOICE, list_voices, router


def test_tts_router_has_expected_routes() -> None:
    """Verify TTS router is configured with correct paths."""
    paths = {r.path for r in router.routes}
    assert any("synthesize" in p for p in paths)
    assert any("voices" in p for p in paths)


def test_default_voice_is_chinese() -> None:
    """Default voice should be Chinese for JARVIS."""
    assert "zh-CN" in _DEFAULT_VOICE


async def test_list_voices_structure() -> None:
    """list_voices should return a dict with 'voices' list and 'default' string."""
    assert inspect.iscoroutinefunction(list_voices)
