"""Tests for voice WebSocket endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

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
    from app.api.voice import transcribe_audio

    mock_transcript = MagicMock()
    mock_transcript.text = "Hello world"

    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_transcript)

    with patch("app.api.voice.openai.AsyncOpenAI", return_value=mock_client):
        result = await transcribe_audio(b"fake audio", "sk-test")

    assert result == "Hello world"
    mock_client.audio.transcriptions.create.assert_called_once()


def test_voice_rejects_missing_token():
    """WebSocket connection without token is rejected (missing required param)."""
    from starlette.testclient import TestClient

    from app.main import app

    with TestClient(app) as tc:
        with pytest.raises(Exception):  # noqa: B017
            with tc.websocket_connect("/api/voice/stream"):
                pass


def test_voice_sends_error_on_stt_failure():
    """When STT fails, server sends an error JSON over the WebSocket."""
    import uuid

    from starlette.testclient import TestClient

    from app.api.deps import get_current_user_query_token
    from app.db.session import get_db
    from app.main import app

    mock_user = MagicMock()
    mock_user.id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=None)  # No UserSettings

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_current_user_query_token] = lambda: mock_user
    app.dependency_overrides[get_db] = _override_db
    try:
        with (
            patch(
                "app.api.voice.transcribe_audio",
                new=AsyncMock(side_effect=Exception("STT failed")),
            ),
            patch("app.api.voice.build_rag_context", new=AsyncMock(return_value="")),
            patch("app.api.voice.create_graph"),
        ):
            with TestClient(app) as tc:
                with tc.websocket_connect("/api/voice/stream?token=fake") as ws:
                    ws.send_bytes(b"fake audio data")
                    msg = ws.receive_json()
        assert msg["type"] == "error"
    finally:
        app.dependency_overrides.clear()
