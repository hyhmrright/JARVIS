import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm_config import ResolvedLLMConfig
from app.core.security import decode_access_token
from app.db.models import (
    ApiKey,
    User,
    UserRole,
    Workspace,
    WorkspaceMember,
)
from app.db.session import get_db, isolated_session

security = HTTPBearer()


class PaginationParams:
    """Reusable pagination dependency for list endpoints.

    Usage::

        @router.get("/items")
        async def list_items(p: Annotated[PaginationParams, Depends()]):
            return db.query(...).offset(p.skip).limit(p.limit).all()

    Individual routes may override the default ``limit`` by subclassing or
    adding their own ``Query`` parameters — but they should use this class as
    the baseline so all endpoints share the same skip/limit semantics.
    """

    def __init__(
        self,
        skip: Annotated[int, Query(ge=0, description="Number of records to skip")] = 0,
        limit: Annotated[
            int, Query(ge=1, le=200, description="Maximum records to return")
        ] = 50,
    ) -> None:
        self.skip = skip
        self.limit = limit


async def _resolve_user(
    token: str,
    db: AsyncSession,
    request: Request = None,  # type: ignore[assignment]
) -> User:
    """Authenticate by JWT or PAT token and return the active user.

    PAT tokens start with ``jv_``. Scope is stored in
    ``request.state.api_key_scope`` for optional downstream enforcement.
    JWT tokens always get scope ``full``.
    """
    if token.startswith("jv_"):
        return await _resolve_pat(token, db, request)
    return await _resolve_jwt(token, db, request)


async def _resolve_jwt(
    token: str,
    db: AsyncSession,
    request: Request = None,  # type: ignore[assignment]
) -> User:
    try:
        user_id = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc
    user = await db.scalar(
        select(User).where(User.id == user_id, User.is_active == True)  # noqa: E712
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if request is not None:
        request.state.api_key_scope = "full"
    return user


async def _resolve_pat(
    token: str,
    db: AsyncSession,
    request: Request = None,  # type: ignore[assignment]
) -> User:
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    api_key = await db.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash))
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )
    if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired"
        )
    user = await db.scalar(
        select(User).where(User.id == api_key.user_id, User.is_active == True)  # noqa: E712
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    # Update last_used_at in an isolated session to avoid committing the
    # shared request session from within the auth dependency.
    async with isolated_session() as _session:
        result = await _session.scalar(select(ApiKey).where(ApiKey.id == api_key.id))
        if result is not None:
            result.last_used_at = datetime.now(UTC)
    if request is not None:
        request.state.api_key_scope = api_key.scope
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
) -> User:
    return await _resolve_user(credentials.credentials, db, request)


async def resolve_user_token(
    token: str,
    db: AsyncSession,
    request: Request = None,  # type: ignore[assignment]
) -> User:
    """Resolve a JWT or PAT token outside standard header/query dependencies."""
    return await _resolve_user(token, db, request)


_security_optional = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security_optional),
    db: AsyncSession = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
) -> "User | None":
    """Like get_current_user but returns None instead of raising 401."""
    if not credentials:
        return None
    try:
        return await _resolve_user(credentials.credentials, db, request)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


async def get_current_user_query_token(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
) -> User:
    """Authenticate via ?token= query param (for SSE endpoints where headers
    aren't supported)."""
    return await _resolve_user(token, db, request)


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """Ensure the current user has administrative privileges."""
    if user.role not in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def require_workspace_member(
    workspace_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> None:
    """Raise 404 if workspace not found or cross-org, 403 if user is not a member.

    This is the canonical workspace access guard used across all API modules.
    The 404/403 split is intentional: cross-org workspaces return 404 to avoid
    leaking workspace existence to users outside the organization.
    """
    workspace = await db.get(Workspace, workspace_id)
    if (
        workspace is None
        or workspace.is_deleted
        or workspace.organization_id != user.organization_id
    ):
        raise HTTPException(status_code=404, detail="Workspace not found")
    membership = await db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=403, detail="You are not a member of this workspace"
        )


async def get_llm_config(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    workspace_id: uuid.UUID | None = None,
) -> ResolvedLLMConfig:
    """Load user LLM settings and resolve a valid API key using ConfigService."""
    from app.services.config_service import ConfigService

    service = ConfigService(db)
    config = await service.get_llm_config(user.id, workspace_id)

    # Validation for API layer
    if config.api_key == "missing":
        raise HTTPException(
            status_code=400,
            detail=f"No API key configured for provider '{config.provider}'. "
            "Set it in Settings or ask the admin to configure a server-level key.",
        )
    return config
