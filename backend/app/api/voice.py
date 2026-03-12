"""Voice WebSocket: JWT auth + Whisper STT + user LLM settings + edge-TTS."""

import io
from dataclasses import dataclass
from typing import Any

import edge_tts
import openai
import structlog
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import create_graph
from app.agent.persona import build_system_prompt
from app.agent.state import AgentState
from app.api.deps import get_current_user_query_token
from app.core.config import settings
from app.core.permissions import DEFAULT_ENABLED_TOOLS
from app.core.security import resolve_api_key, resolve_api_keys
from app.db.models import User, UserSettings
from app.db.session import get_db
from app.rag.context import build_rag_context

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/voice", tags=["voice"])

_TTS_VOICE_MAP: dict[str, str] = {
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-JennyNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
}
_DEFAULT_TTS_VOICE = "zh-CN-XiaoxiaoNeural"


@dataclass
class _VoiceSessionConfig:
    provider: str
    model_name: str
    api_keys: list[str]
    openai_key: str | None
    persona: str | None
    enabled: list[str] | None
    tts_voice: str
    user_id: str


def _get_tts_voice(locale: str) -> str:
    """Return edge-tts voice name for the given locale prefix."""
    return _TTS_VOICE_MAP.get(locale[:2].lower(), _DEFAULT_TTS_VOICE)


async def transcribe_audio(audio_bytes: bytes, openai_key: str) -> str:
    """Call OpenAI Whisper API and return transcript text."""
    client = openai.AsyncOpenAI(api_key=openai_key)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.webm"
    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )
    return transcript.text


async def _stream_llm_reply(
    websocket: WebSocket,
    cfg: _VoiceSessionConfig,
    user_text: str,
    rag_context: str,
) -> str:
    """Run the LLM graph, stream deltas, and return the full reply."""
    if not cfg.api_keys:
        return ""

    system_content = build_system_prompt(cfg.persona)
    lc_messages: list[Any] = [SystemMessage(content=system_content)]
    if rag_context:
        lc_messages.append(SystemMessage(content=rag_context))
    lc_messages.append(HumanMessage(content=user_text))

    graph = create_graph(
        provider=cfg.provider,
        model=cfg.model_name,
        api_key=cfg.api_keys[0],
        enabled_tools=cfg.enabled,
        api_keys=cfg.api_keys,
        user_id=cfg.user_id,
        openai_api_key=cfg.openai_key,
        tavily_api_key=settings.tavily_api_key,
    )

    full_reply = ""
    prev_content = ""
    async for chunk in graph.astream(AgentState(messages=lc_messages)):
        if "llm" in chunk:
            msg = chunk["llm"]["messages"][-1]
            if msg.content:
                new_content = str(msg.content)
                # Reset prev_content per LLM node pass so that tool-call
                # interleaving does not carry the cursor from a previous pass.
                delta = new_content[len(prev_content) :]
                prev_content = new_content
                full_reply += delta
                if delta:
                    await websocket.send_json({"type": "ai_text_delta", "delta": delta})
        else:
            # A non-llm node (e.g. tools) has run; reset the per-pass cursor so
            # the next LLM node entry starts fresh.
            prev_content = ""
    return full_reply


async def _handle_turn(
    websocket: WebSocket,
    cfg: _VoiceSessionConfig,
    audio_bytes: bytes,
) -> None:
    """Handle a single voice turn: STT → LLM → TTS."""
    if not cfg.openai_key:
        await websocket.send_json(
            {
                "type": "error",
                "message": "OpenAI API key required for speech recognition.",
            }
        )
        return
    try:
        user_text = await transcribe_audio(audio_bytes, cfg.openai_key)
    except Exception as exc:
        logger.warning("voice_stt_failed", error=str(exc))
        await websocket.send_json(
            {"type": "error", "message": "Speech recognition failed."}
        )
        return

    await websocket.send_json({"type": "transcription", "text": user_text})

    rag_context = await build_rag_context(cfg.user_id, user_text, cfg.openai_key)

    if not cfg.api_keys:
        await websocket.send_json(
            {"type": "error", "message": "No LLM API key configured."}
        )
        return

    full_reply = await _stream_llm_reply(websocket, cfg, user_text, rag_context)

    if full_reply:
        communicate = edge_tts.Communicate(full_reply, cfg.tts_voice)
        async for tts_chunk in communicate.stream():
            if tts_chunk["type"] == "audio" and tts_chunk.get("data"):
                await websocket.send_bytes(tts_chunk["data"])

    await websocket.send_json({"type": "done"})


@router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    locale: str = Query(default="zh"),
    user: User = Depends(get_current_user_query_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    """WebSocket for real-time voice interaction.

    Protocol:
    - Client connects with ?token=<jwt>[&locale=<zh|en|ja|...>]
    - Client sends binary audio chunks (WebM)
    - Server sends JSON: {"type": "transcription", "text": "..."}
    - Server sends JSON: {"type": "ai_text_delta", "delta": "..."}
    - Server sends binary audio response (MP3 chunks)
    - Server sends JSON: {"type": "done"}
    - Server sends JSON: {"type": "error", "message": "..."} on failure
    """
    await websocket.accept()
    logger.info("voice_websocket_connected", user_id=str(user.id))

    us = await db.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    raw_keys = us.api_keys if us else {}
    cfg = _VoiceSessionConfig(
        provider=us.model_provider if us else "deepseek",
        model_name=us.model_name if us else "deepseek-chat",
        api_keys=resolve_api_keys(us.model_provider if us else "deepseek", raw_keys),
        openai_key=resolve_api_key("openai", raw_keys),
        persona=us.persona_override if us else None,
        enabled=(
            us.enabled_tools
            if us and us.enabled_tools is not None
            else DEFAULT_ENABLED_TOOLS
        ),
        tts_voice=_get_tts_voice(locale),
        user_id=str(user.id),
    )

    try:
        while True:
            audio_bytes = await websocket.receive_bytes()
            await _handle_turn(websocket, cfg, audio_bytes)
    except WebSocketDisconnect:
        logger.info("voice_websocket_disconnected", user_id=str(user.id))
    except Exception:
        logger.exception("voice_websocket_error", user_id=str(user.id))
        try:
            await websocket.send_json(
                {"type": "error", "message": "Internal server error."}
            )
        except Exception:
            pass
