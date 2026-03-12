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


def test_voice_rejects_missing_token(db_session):
    """WebSocket connection without token closes with an error (missing param)."""
    from starlette.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as tc:
            with pytest.raises(Exception):  # noqa: B017
                with tc.websocket_connect("/api/voice/stream"):
                    pass  # Should fail: missing token query param
    finally:
        app.dependency_overrides.clear()


def test_voice_sends_error_on_stt_failure(db_session):
    """When STT fails, server sends an error JSON message over the WebSocket."""
    import uuid

    from starlette.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    email = f"voice_{uuid.uuid4().hex[:8]}@example.com"
    try:
        with TestClient(app) as tc:
            resp = tc.post(
                "/api/auth/register",
                json={"email": email, "password": "password123"},
            )
            assert resp.status_code == 201
            token = resp.json()["access_token"]

            with (
                patch(
                    "app.api.voice.transcribe_audio",
                    new=AsyncMock(side_effect=Exception("STT failed")),
                ),
                patch(
                    "app.api.voice.build_rag_context", new=AsyncMock(return_value="")
                ),
                patch("app.api.voice.create_graph"),
            ):
                with tc.websocket_connect(f"/api/voice/stream?token={token}") as ws:
                    ws.send_bytes(b"fake audio data")
                    msg = ws.receive_json()
        assert msg["type"] == "error"
    finally:
        app.dependency_overrides.clear()
