"""Unit tests for the centralized authorization service."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.services.authorization import (
    assert_doc_write_access,
    require_org,
    require_workspace_role,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
ORG_ID = UUID("00000000-0000-0000-0000-000000000002")
WS_ID = UUID("00000000-0000-0000-0000-000000000003")
DOC_ID = UUID("00000000-0000-0000-0000-000000000004")


def _make_user(org_id: UUID | None = ORG_ID) -> MagicMock:
    user = MagicMock()
    user.id = USER_ID
    user.organization_id = org_id
    return user


def _make_db(scalar_return=None, get_return=None) -> AsyncMock:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=scalar_return)
    db.get = AsyncMock(return_value=get_return)
    return db


# ---------------------------------------------------------------------------
# require_org
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_require_org_no_org_id_raises_403() -> None:
    user = _make_user(org_id=None)
    db = _make_db()
    with pytest.raises(HTTPException) as exc_info:
        await require_org(user, db)
    assert exc_info.value.status_code == 403
    assert "organization" in exc_info.value.detail.lower()


@pytest.mark.anyio
async def test_require_org_org_not_found_raises_403() -> None:
    user = _make_user()
    db = _make_db(get_return=None)
    with pytest.raises(HTTPException) as exc_info:
        await require_org(user, db)
    assert exc_info.value.status_code == 403
    assert "not found" in exc_info.value.detail.lower()


@pytest.mark.anyio
async def test_require_org_success_returns_org() -> None:
    user = _make_user()
    org = MagicMock()
    org.id = ORG_ID
    db = _make_db(get_return=org)
    result = await require_org(user, db)
    assert result is org


# ---------------------------------------------------------------------------
# require_workspace_role
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_require_workspace_role_no_membership_raises_403() -> None:
    db = _make_db(scalar_return=None)
    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_role(workspace_id=WS_ID, user_id=USER_ID, db=db)
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_require_workspace_role_wrong_role_raises_403() -> None:
    membership = MagicMock()
    membership.role = "member"
    db = _make_db(scalar_return=membership)
    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_role(workspace_id=WS_ID, user_id=USER_ID, db=db)
    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_require_workspace_role_owner_returns_membership() -> None:
    membership = MagicMock()
    membership.role = "owner"
    db = _make_db(scalar_return=membership)
    result = await require_workspace_role(workspace_id=WS_ID, user_id=USER_ID, db=db)
    assert result is membership


@pytest.mark.anyio
async def test_require_workspace_role_admin_returns_membership() -> None:
    membership = MagicMock()
    membership.role = "admin"
    db = _make_db(scalar_return=membership)
    result = await require_workspace_role(workspace_id=WS_ID, user_id=USER_ID, db=db)
    assert result is membership


@pytest.mark.anyio
async def test_require_workspace_role_custom_allowed_roles() -> None:
    membership = MagicMock()
    membership.role = "member"
    db = _make_db(scalar_return=membership)
    # member is allowed when we pass a custom frozenset
    result = await require_workspace_role(
        workspace_id=WS_ID,
        user_id=USER_ID,
        db=db,
        allowed_roles=frozenset({"member", "admin"}),
    )
    assert result is membership


# ---------------------------------------------------------------------------
# assert_doc_write_access
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_assert_doc_write_access_personal_owner_ok() -> None:
    user = _make_user()
    doc = MagicMock()
    doc.workspace_id = None
    doc.user_id = USER_ID
    db = _make_db()
    # Should not raise
    await assert_doc_write_access(doc, user, db)


@pytest.mark.anyio
async def test_assert_doc_write_access_personal_non_owner_raises_404() -> None:
    user = _make_user()
    doc = MagicMock()
    doc.workspace_id = None
    doc.user_id = uuid4()  # different user
    db = _make_db()
    with pytest.raises(HTTPException) as exc_info:
        await assert_doc_write_access(doc, user, db)
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_assert_doc_write_access_workspace_admin_ok() -> None:
    user = _make_user()
    doc = MagicMock()
    doc.workspace_id = WS_ID
    membership = MagicMock()
    membership.role = "admin"
    db = _make_db(scalar_return=membership)
    # Should not raise
    await assert_doc_write_access(doc, user, db)


@pytest.mark.anyio
async def test_assert_doc_write_access_workspace_member_raises_403() -> None:
    user = _make_user()
    doc = MagicMock()
    doc.workspace_id = WS_ID
    membership = MagicMock()
    membership.role = "member"
    db = _make_db(scalar_return=membership)
    with pytest.raises(HTTPException) as exc_info:
        await assert_doc_write_access(doc, user, db)
    assert exc_info.value.status_code == 403
