import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import create_graph
from app.agent.state import AgentState
from app.api.deps import get_current_user
from app.db.models import Conversation, Message, User, UserSettings
from app.db.session import get_db

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    content: str


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404)

    user_settings = await db.scalar(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    provider = user_settings.model_provider if user_settings else "deepseek"
    model_name = user_settings.model_name if user_settings else "deepseek-chat"
    api_keys = user_settings.api_keys if user_settings else {}
    api_key = api_keys.get(provider, "")

    db.add(Message(conversation_id=conv.id, role="human", content=body.content))
    await db.commit()

    history = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    lc_messages = [
        HumanMessage(content=msg.content)
        for msg in history.all()
        if msg.role == "human"
    ]

    async def generate():
        graph = create_graph(provider=provider, model=model_name, api_key=api_key)
        full_content = ""
        async for chunk in graph.astream(AgentState(messages=lc_messages)):
            if "llm" in chunk:
                ai_msg = chunk["llm"]["messages"][-1]
                full_content = ai_msg.content
                data = json.dumps({"content": full_content})
                yield "data: " + data + "\n\n"
        async with db.begin():
            db.add(
                Message(
                    conversation_id=conv.id,
                    role="ai",
                    content=full_content,
                    model_provider=provider,
                    model_name=model_name,
                )
            )

    return StreamingResponse(generate(), media_type="text/event-stream")
