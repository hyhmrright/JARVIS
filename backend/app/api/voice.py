import edge_tts
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.graph import create_graph
from app.agent.persona import build_system_prompt
from app.agent.state import AgentState
from app.core.config import settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket) -> None:
    """WebSocket for real-time voice interaction (OpenClaw style).

    Protocol:
    - Client sends binary audio chunks (WebM/WAV)
    - Server sends JSON: {"type": "transcription", "text": "..."}
    - Server sends JSON: {"type": "ai_text", "text": "..."}
    - Server sends binary audio response (MP3)
    """
    await websocket.accept()
    logger.info("voice_websocket_connected")

    # For now, we assume simple turn-based but over WS for streaming
    try:
        while True:
            # 1. Receive data (expecting binary for now)
            _data = await websocket.receive_bytes()

            # TODO: Integrate Whisper for STT. Currently placeholder logic.

            # In a real OpenClaw implementation, we'd pipe this to a Whisper stream.
            user_text = "Hello, what can you do?"  # Placeholder

            await websocket.send_json({"type": "transcription", "text": user_text})

            # 2. Run Agent (simplified for WS)
            # In production, we'd resolve user and LLM config from initial auth message
            system_msg = SystemMessage(content=build_system_prompt(None))
            lc_messages = [system_msg, HumanMessage(content=user_text)]

            # Hardcoded defaults for demo logic in WS
            # (In reality, use deps or session data)
            graph = create_graph(
                provider="deepseek",
                model="deepseek-chat",
                api_key=settings.deepseek_api_key,
                user_id="voice-user",
            )

            full_reply = ""
            async for chunk in graph.astream(AgentState(messages=lc_messages)):
                if "llm" in chunk:
                    msg = chunk["llm"]["messages"][-1]
                    if msg.content:
                        # Extract new content delta
                        delta = str(msg.content)[len(full_reply) :]
                        full_reply = str(msg.content)
                        if delta:
                            await websocket.send_json(
                                {"type": "ai_text_delta", "delta": delta}
                            )

            # 3. TTS Response (Streaming)
            communicate = edge_tts.Communicate(full_reply, "zh-CN-XiaoxiaoNeural")
            async for tts_chunk in communicate.stream():
                if tts_chunk["type"] == "audio" and tts_chunk.get("data"):
                    # Send binary audio chunk directly
                    await websocket.send_bytes(tts_chunk["data"])

            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        logger.info("voice_websocket_disconnected")
    except Exception:
        logger.exception("voice_websocket_error")
