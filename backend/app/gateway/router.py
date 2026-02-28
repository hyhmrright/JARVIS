import re

import structlog

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
    ) -> None:
        self._registry = registry
        self._session_manager = session_manager
        self._pairing_manager = pairing_manager

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
        reply = await self._run_agent(user_id=user_id, message=msg)

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

    async def _run_agent(self, user_id: str, message: GatewayMessage) -> str:
        """Stub agent runner — override or inject a real implementation.

        TODO(phase4+): Wire in create_graph() + AgentState during agent
        integration phase.  See roadmap task 4.x for details.
        """
        return (
            "Your account is linked, but the AI agent is not yet available. "
            "This feature is coming soon!"
        )
