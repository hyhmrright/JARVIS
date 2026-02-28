import re
import uuid
from typing import Any

import structlog
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.compressor import compact_messages
from app.agent.graph import create_graph
from app.agent.persona import build_system_prompt
from app.agent.state import AgentState
from app.core.config import settings
from app.core.permissions import DEFAULT_ENABLED_TOOLS
from app.core.security import resolve_api_key, resolve_api_keys
from app.db.models import Conversation, Message, UserSettings
from app.gateway.channel_registry import ChannelRegistry
from app.gateway.models import GatewayMessage
from app.gateway.security import (
    PAIRING_INVALID,
    PAIRING_PROMPT,
    PAIRING_SUCCESS,
    PairingManager,
)
from app.gateway.session_manager import SessionManager

logger = structlog.get_logger(__name__)

_CODE_RE = re.compile(r"^\s*(\d{6})\s*$")
_ROLE_TO_MESSAGE = {"human": HumanMessage, "ai": AIMessage}


class GatewayRouter:
    """Routes incoming messages from any channel to the appropriate agent session.

    The router is intentionally kept thin: it resolves the session, delegates
    to a pluggable agent callable, and returns the reply string.  The actual
    LangGraph invocation lives outside this class so it can be replaced in
    tests without heavy mocking.

    Unauthenticated senders receive a pairing prompt.  If their message looks
    like a 6-digit code, the router attempts to validate it via
    ``PairingManager`` and links the session on success.
    """

    def __init__(
        self,
        registry: ChannelRegistry,
        session_manager: SessionManager,
        pairing_manager: PairingManager | None = None,
        *,
        db_session_factory: type[AsyncSession] | None = None,
    ) -> None:
        self._registry = registry
        self._session_manager = session_manager
        self._pairing_manager = pairing_manager
        self._db_session_factory = db_session_factory

    async def handle_message(self, msg: GatewayMessage) -> str:
        """Process an inbound GatewayMessage and return the agent reply.

        Raises ValueError if the originating channel is not registered.

        For unauthenticated senders:
        - If the message is a 6-digit code *and* a PairingManager is wired in,
          attempt validation and link the session on success.
        - Otherwise return the pairing prompt.
        """
        adapter = self._registry.get(msg.channel)
        if adapter is None:
            raise ValueError(f"Unknown channel: {msg.channel!r}")

        session = await self._session_manager.get_or_create_session(
            sender_id=msg.sender_id, channel=msg.channel
        )
        user_id: str | None = session.get("user_id")

        logger.info(
            "gateway_message_received",
            channel=msg.channel,
            sender_id=msg.sender_id,
            user_id=user_id,
            content_length=len(msg.content),
        )

        if user_id is None:
            return await self._handle_unauthenticated(msg)

        # Delegate to the agent runner registered on this router.
        reply = await self._run_agent(user_id=user_id, message=msg, session=session)

        logger.info(
            "gateway_message_handled",
            channel=msg.channel,
            sender_id=msg.sender_id,
            reply_chars=len(reply),
        )
        return reply

    async def _handle_unauthenticated(self, msg: GatewayMessage) -> str:
        """Handle a message from a sender with no linked JARVIS account.

        If the message looks like a 6-digit pairing code, attempt to validate
        it and link the session.  Otherwise return the pairing prompt.
        """
        logger.warning(
            "gateway_unauthenticated",
            channel=msg.channel,
            sender_id=msg.sender_id,
        )

        match = _CODE_RE.match(msg.content)
        if match and self._pairing_manager is not None:
            code = match.group(1)
            linked_user_id = await self._pairing_manager.validate_code(code)
            if linked_user_id is not None:
                await self._session_manager.link_user(
                    sender_id=msg.sender_id,
                    channel=msg.channel,
                    user_id=linked_user_id,
                )
                logger.info(
                    "gateway_pairing_success",
                    channel=msg.channel,
                    sender_id=msg.sender_id,
                    user_id=linked_user_id,
                )
                return PAIRING_SUCCESS
            # Code was 6 digits but didn't match anything in Redis.
            logger.warning(
                "gateway_pairing_failed",
                channel=msg.channel,
                sender_id=msg.sender_id,
            )
            return PAIRING_INVALID

        return PAIRING_PROMPT

    async def _run_agent(
        self,
        user_id: str,
        message: GatewayMessage,
        session: dict[str, Any] | None = None,
    ) -> str:
        """Run the LangGraph agent for a paired gateway user.

        Loads user settings from DB, resolves API keys, fetches or creates a
        gateway conversation, then invokes the agent graph and persists both
        the user message and the AI reply.
        """
        if self._db_session_factory is None:
            from app.db.session import AsyncSessionLocal

            self._db_session_factory = AsyncSessionLocal  # type: ignore[assignment]

        async with self._db_session_factory() as db:  # type: ignore[misc]
            (
                provider,
                model_name,
                raw_keys,
                persona_override,
                enabled_tools,
            ) = await self._load_user_settings(db, user_id)

            api_keys = resolve_api_keys(provider, raw_keys)
            if not api_keys:
                return (
                    "No API key configured for your account. "
                    "Please set one in Settings."
                )

            conv = await self._resolve_conversation(db, user_id, message, session)

            lc_messages = await self._build_message_history(db, conv, persona_override)

            # Compress long histories before invoking the agent
            try:
                lc_messages = await compact_messages(
                    lc_messages,
                    provider=provider,
                    model=model_name,
                    api_key=api_keys[0],
                )
            except Exception:
                logger.warning(
                    "gateway_compression_failed",
                    exc_info=True,
                )

            ai_content = await self._invoke_agent(
                provider=provider,
                model_name=model_name,
                api_keys=api_keys,
                raw_keys=raw_keys,
                enabled_tools=enabled_tools,
                user_id=user_id,
                lc_messages=lc_messages,
                channel=message.channel,
            )

            # Persist AI response
            db.add(
                Message(
                    conversation_id=conv.id,
                    role="ai",
                    content=ai_content,
                    model_provider=provider,
                    model_name=model_name,
                )
            )
            await db.commit()

            logger.info(
                "gateway_agent_completed",
                user_id=user_id,
                channel=message.channel,
                reply_chars=len(ai_content),
            )
            return ai_content

    # -- private helpers (extracted from _run_agent) -------------------------

    async def _load_user_settings(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> tuple[str, str, dict, str | None, list[str]]:
        """Load user settings, returning defaults when absent."""
        us = await db.scalar(
            select(UserSettings).where(UserSettings.user_id == uuid.UUID(user_id))
        )
        if us is None:
            return (
                "deepseek",
                "deepseek-chat",
                {},
                None,
                DEFAULT_ENABLED_TOOLS,
            )
        enabled = (
            us.enabled_tools if us.enabled_tools is not None else DEFAULT_ENABLED_TOOLS
        )
        return (
            us.model_provider,
            us.model_name,
            us.api_keys,
            us.persona_override,
            enabled,
        )

    async def _resolve_conversation(
        self,
        db: AsyncSession,
        user_id: str,
        message: GatewayMessage,
        session: dict[str, Any] | None,
    ) -> Conversation:
        """Fetch or create the gateway conversation and persist the user message."""
        if session is None:
            session = await self._session_manager.get_or_create_session(
                sender_id=message.sender_id, channel=message.channel
            )
        conv_id_str: str | None = session.get("conversation_id")
        conv = (
            await db.get(Conversation, uuid.UUID(conv_id_str)) if conv_id_str else None
        )

        if conv is None:
            conv = Conversation(
                user_id=uuid.UUID(user_id),
                title=f"Gateway ({message.channel})",
            )
            db.add(conv)
            await db.flush()
            await self._session_manager.update_session(
                sender_id=message.sender_id,
                channel=message.channel,
                conversation_id=str(conv.id),
            )

        # Persist user message
        db.add(
            Message(
                conversation_id=conv.id,
                role="human",
                content=message.content,
            )
        )
        await db.flush()
        return conv

    async def _build_message_history(
        self,
        db: AsyncSession,
        conv: Conversation,
        persona_override: str | None,
    ) -> list[BaseMessage]:
        """Build the LangChain message list from DB rows."""
        rows = await db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at)
        )
        lc_messages: list[BaseMessage] = [
            SystemMessage(content=build_system_prompt(persona_override))
        ]
        for row in rows.all():
            cls = _ROLE_TO_MESSAGE.get(row.role)
            if cls:
                lc_messages.append(cls(content=row.content))
        return lc_messages

    async def _invoke_agent(
        self,
        *,
        provider: str,
        model_name: str,
        api_keys: list[str],
        raw_keys: dict,
        enabled_tools: list[str],
        user_id: str,
        lc_messages: list[BaseMessage],
        channel: str,
    ) -> str:
        """Create and invoke the LangGraph agent, returning the AI reply."""
        graph = create_graph(
            provider=provider,
            model=model_name,
            api_key=api_keys[0],
            enabled_tools=enabled_tools,
            api_keys=api_keys,
            user_id=user_id,
            openai_api_key=resolve_api_key("openai", raw_keys),
            tavily_api_key=settings.tavily_api_key,
        )

        try:
            result = await graph.ainvoke(AgentState(messages=lc_messages))
            return str(result["messages"][-1].content)
        except Exception:
            logger.exception(
                "gateway_agent_error",
                user_id=user_id,
                channel=channel,
            )
            return (
                "Sorry, an error occurred while processing "
                "your request. Please try again."
            )
