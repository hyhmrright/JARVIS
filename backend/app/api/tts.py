"""Text-to-speech synthesis using edge-tts (Microsoft neural voices)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import edge_tts
import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.db.models import User

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/tts", tags=["tts"])

_DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice: str = _DEFAULT_VOICE
    rate: str = "+0%"


@router.post("/synthesize")
async def synthesize(
    body: TTSRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Synthesize text to speech and stream MP3 audio."""

    async def _stream() -> AsyncGenerator[bytes]:
        communicate = edge_tts.Communicate(body.text, body.voice, rate=body.rate)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio" and chunk.get("data"):
                yield chunk["data"]

    logger.info(
        "tts_synthesize",
        user_id=str(user.id),
        voice=body.voice,
        chars=len(body.text),
    )
    return StreamingResponse(
        _stream(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/voices")
async def list_voices(user: User = Depends(get_current_user)) -> dict:
    """Return available TTS voices."""
    return {
        "voices": [
            {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓 (中文)", "lang": "zh"},
            {"id": "zh-CN-YunxiNeural", "name": "云希 (中文)", "lang": "zh"},
            {"id": "en-US-JennyNeural", "name": "Jenny (English)", "lang": "en"},
            {"id": "ja-JP-NanamiNeural", "name": "七海 (日本語)", "lang": "ja"},
        ],
        "default": _DEFAULT_VOICE,
    }
