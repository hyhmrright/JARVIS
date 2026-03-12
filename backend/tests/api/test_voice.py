"""Tests for voice WebSocket endpoint."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_tts_voice_mapping():
    """TTS voice is selected based on locale parameter."""
    from app.api.voice import _get_tts_voice

    assert _get_tts_voice("zh") == "zh-CN-XiaoxiaoNeural"
    assert _get_tts_voice("en") == "en-US-JennyNeural"
    assert _get_tts_voice("ja") == "ja-JP-NanamiNeural"
    assert _get_tts_voice("unknown") == "zh-CN-XiaoxiaoNeural"
    assert _get_tts_voice("ZH") == "zh-CN-XiaoxiaoNeural"  # case-insensitive


@pytest.mark.asyncio
async def test_transcribe_audio_calls_whisper():
    """transcribe_audio calls OpenAI Whisper and returns text."""
    from unittest.mock import MagicMock

    from app.api.voice import transcribe_audio

    mock_transcript = MagicMock()
    mock_transcript.text = "Hello world"

    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_transcript)

    with patch("app.api.voice.openai.AsyncOpenAI", return_value=mock_client):
        result = await transcribe_audio(b"fake audio", "sk-test")

    assert result == "Hello world"
    mock_client.audio.transcriptions.create.assert_called_once()
