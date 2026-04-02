"""Unit tests for WorkspaceService."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.workspace_service import WorkspaceService


def _make_user(org_id: uuid.UUID | None = None) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.organization_id = org_id or uuid.uuid4()
    return user


def _make_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


# ---------------------------------------------------------------------------
# create_workspace
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_workspace_success():
    org_id = uuid.uuid4()
    user = _make_user(org_id)

    org = MagicMock()
    org.id = org_id

    db = _make_db()

    async def fake_refresh(obj: object) -> None:
        pass

    db.refresh = fake_refresh

    with patch(
        "app.services.workspace_service.require_org", new=AsyncMock(return_value=org)
    ):
        svc = WorkspaceService(db)
        result = await svc.create_workspace(user=user, name="MyWS")

    db.add.assert_called_once()
    db.commit.assert_called_once()
    assert result is not None


# ---------------------------------------------------------------------------
# update_workspace
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_update_workspace_not_found_raises_404():
    user = _make_user()
    db = _make_db()
    db.get = AsyncMock(return_value=None)

    svc = WorkspaceService(db)
    with pytest.raises(HTTPException) as exc_info:
        await svc.update_workspace(ws_id=uuid.uuid4(), user=user, name="new")
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_update_workspace_deleted_raises_404():
    user = _make_user()
    ws = MagicMock()
    ws.is_deleted = True

    db = _make_db()
    db.get = AsyncMock(return_value=ws)

    svc = WorkspaceService(db)
    with pytest.raises(HTTPException) as exc_info:
        await svc.update_workspace(ws_id=uuid.uuid4(), user=user, name="new")
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_update_workspace_wrong_org_raises_403():
    user = _make_user(uuid.uuid4())
    ws = MagicMock()
    ws.is_deleted = False
    ws.organization_id = uuid.uuid4()  # different from user.organization_id

    db = _make_db()
    db.get = AsyncMock(return_value=ws)

    svc = WorkspaceService(db)
    with pytest.raises(HTTPException) as exc_info:
        await svc.update_workspace(ws_id=uuid.uuid4(), user=user, name="new")
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# delete_workspace
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_delete_workspace_non_owner_raises_403():
    org_id = uuid.uuid4()
    user = _make_user(org_id)
    user.id = uuid.uuid4()

    org = MagicMock()
    org.id = org_id
    org.owner_id = uuid.uuid4()  # different from user.id

    ws = MagicMock()
    ws.is_deleted = False
    ws.organization_id = org_id

    db = _make_db()
    db.get = AsyncMock(return_value=ws)

    with patch(
        "app.services.workspace_service.require_org", new=AsyncMock(return_value=org)
    ):
        svc = WorkspaceService(db)
        with pytest.raises(HTTPException) as exc_info:
            await svc.delete_workspace(ws_id=uuid.uuid4(), user=user)
    assert exc_info.value.status_code == 403
    assert "owner" in exc_info.value.detail


@pytest.mark.anyio
async def test_delete_workspace_not_found_raises_404():
    user = _make_user()
    org = MagicMock()
    org.id = user.organization_id

    db = _make_db()
    db.get = AsyncMock(return_value=None)

    with patch(
        "app.services.workspace_service.require_org", new=AsyncMock(return_value=org)
    ):
        svc = WorkspaceService(db)
        with pytest.raises(HTTPException) as exc_info:
            await svc.delete_workspace(ws_id=uuid.uuid4(), user=user)
    assert exc_info.value.status_code == 404
