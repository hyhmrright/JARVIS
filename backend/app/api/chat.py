import json
import uuid
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import create_graph
from app.agent.persona import build_system_prompt
from app.agent.state import AgentState
from app.api.deps import ResolvedLLMConfig, get_current_user, get_llm_config
from app.db.models import Conversation, Message, User
from app.db.session import AsyncSessionLocal, get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

_ROLE_TO_MESSAGE = {"human": HumanMessage, "ai": AIMessage}


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    content: str = Field(max_length=50000)


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    llm: ResolvedLLMConfig = Depends(get_llm_config),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404)

    db.add(Message(conversation_id=conv.id, role="human", content=body.content))
    await db.commit()

    history_rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    lc_messages = [
        _ROLE_TO_MESSAGE[msg.role](content=msg.content)
        for msg in history_rows.all()
        if msg.role in _ROLE_TO_MESSAGE
    ]

    system_msg = SystemMessage(content=build_system_prompt(llm.persona_override))
    lc_messages = [system_msg, *lc_messages]

    conv_id = conv.id

    logger.info(
        "chat_stream_started",
        user_id=str(user.id),
        conv_id=str(body.conversation_id),
        provider=llm.provider,
        model=llm.model_name,
    )

    async def generate() -> AsyncGenerator[str]:
        graph = create_graph(
            provider=llm.provider,
            model=llm.model_name,
            api_key=llm.api_key,
            enabled_tools=llm.enabled_tools,
        )
        full_content = ""
        try:
            async for chunk in graph.astream(AgentState(messages=lc_messages)):
                if "llm" in chunk:
                    ai_msg = chunk["llm"]["messages"][-1]
                    new_content = ai_msg.content
                    delta = new_content[len(full_content) :]
                    full_content = new_content
                    if delta:
                        data = json.dumps({"delta": delta, "content": full_content})
                        yield "data: " + data + "\n\n"
        except Exception:
            logger.exception("chat_stream_error", conv_id=str(conv_id))
            raise
        finally:
            if full_content:
                try:
                    async with AsyncSessionLocal() as session:
                        async with session.begin():
                            session.add(
                                Message(
                                    conversation_id=conv_id,
                                    role="ai",
                                    content=full_content,
                                    model_provider=llm.provider,
                                    model_name=llm.model_name,
                                )
                            )
                    logger.info(
                        "chat_stream_completed",
                        conv_id=str(conv_id),
                        response_chars=len(full_content),
                    )
                except Exception:
                    logger.exception(
                        "failed_to_save_partial_response",
                        conv_id=str(conv_id),
                    )

    return StreamingResponse(generate(), media_type="text/event-stream")
