"""Agent configuration resolution service.

Consolidates LLM settings loading and API key resolution
previously duplicated in AgentEngine and api/deps.py.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.core.llm_config import ResolvedLLMConfig
from app.core.permissions import DEFAULT_ENABLED_TOOLS
from app.core.security import resolve_api_keys
from app.db.models import UserSettings, WorkspaceMember, WorkspaceSettings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = structlog.get_logger(__name__)


class ConfigService:
    """Domain service for resolving LLM configurations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_llm_config(
        self,
        user_id: uuid.UUID,
        workspace_id: uuid.UUID | None = None,
    ) -> ResolvedLLMConfig:
        """Resolve LLM config for the given user and workspace.

        Resolution order:
          1. User personal keys
          2. Workspace keys (if user is member)
          3. System-level fallback keys
        """
        user_settings = await self._db.scalar(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )

        provider = user_settings.model_provider if user_settings else "deepseek"
        model_name = user_settings.model_name if user_settings else "deepseek-chat"
        raw_keys = user_settings.api_keys if user_settings else {}

        # Tier 1 & 3: Resolve using user keys and system fallbacks
        api_keys = resolve_api_keys(provider, raw_keys)

        # Tier 2: Workspace override
        if not api_keys and workspace_id is not None:
            membership = await self._db.scalar(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == user_id,
                )
            )
            if membership:
                ws_settings = await self._db.scalar(
                    select(WorkspaceSettings).where(
                        WorkspaceSettings.workspace_id == workspace_id
                    )
                )
                if ws_settings:
                    sj = ws_settings.settings_json
                    ws_provider = sj.get("model_provider") or provider
                    ws_model = sj.get("model_name") or model_name
                    ws_raw_keys = sj.get("api_keys", {})
                    ws_api_keys = resolve_api_keys(ws_provider, ws_raw_keys)
                    if ws_api_keys:
                        provider = ws_provider
                        model_name = ws_model
                        raw_keys = ws_raw_keys
                        api_keys = ws_api_keys

        return ResolvedLLMConfig(
            provider=provider,
            model_name=model_name,
            api_key=api_keys[0] if api_keys else "missing",
            api_keys=api_keys,
            enabled_tools=(
                user_settings.enabled_tools
                if user_settings and user_settings.enabled_tools is not None
                else DEFAULT_ENABLED_TOOLS
            ),
            persona_override=user_settings.persona_override if user_settings else None,
            raw_keys=raw_keys,
            base_url=raw_keys.get(f"{provider}_base_url")
            if isinstance(raw_keys.get(f"{provider}_base_url"), str)
            else None,
            temperature=user_settings.temperature if user_settings else 0.7,
            max_tokens=user_settings.max_tokens if user_settings else None,
            system_prompt=user_settings.system_prompt if user_settings else None,
        )
