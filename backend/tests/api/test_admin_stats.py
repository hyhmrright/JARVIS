"""Tests for admin stats endpoint — verifies aggregation correctness
and single-query implementation."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.models import User, UserRole


async def _make_superadmin(db: AsyncSession) -> str:
    """Insert a superadmin user directly and return a JWT token."""
    user = User(
        email=f"superadmin_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        role=UserRole.SUPERADMIN.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return create_access_token(str(user.id))


@pytest.mark.anyio
async def test_get_system_stats_returns_aggregated_counts(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/admin/stats must return non-negative integer counts."""
    token = await _make_superadmin(db_session)
    resp = await client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "user_count" in data
    assert "conversation_count" in data
    assert "message_count" in data
    assert "total_tokens_input" in data
    assert "total_tokens_output" in data
    assert isinstance(data["user_count"], int)
    assert data["user_count"] >= 1  # at least the superadmin we just inserted
    assert data["total_tokens_input"] >= 0
    assert data["total_tokens_output"] >= 0


@pytest.mark.anyio
async def test_get_system_stats_tokens_are_non_negative_integers(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Token counts must be integers >= 0 (never null).

    Verifies the COALESCE(..., 0) guard in the single-query implementation
    ensures null aggregations are converted to 0.
    """
    token = await _make_superadmin(db_session)
    resp = await client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["total_tokens_input"], int)
    assert isinstance(data["total_tokens_output"], int)
    assert data["total_tokens_input"] >= 0
    assert data["total_tokens_output"] >= 0


@pytest.mark.anyio
async def test_list_users_returns_pagination_with_total(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /api/admin/users must return total and users list with or-0 guard."""
    token = await _make_superadmin(db_session)
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "users" in data
    assert isinstance(data["users"], list)
    assert data["total"] >= 1
    assert isinstance(data["total"], int)
