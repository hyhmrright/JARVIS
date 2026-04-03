"""Tests for Workspace and WorkspaceMember domain methods."""

import uuid

from app.db.models.organization import Workspace, WorkspaceMember


def test_workspace_soft_delete():
    ws = Workspace(
        id=uuid.uuid4(), name="Test", organization_id=uuid.uuid4(), is_deleted=False
    )
    assert not ws.is_deleted
    ws.soft_delete()
    assert ws.is_deleted is True


def test_workspace_member_is_privileged_owner():
    m = WorkspaceMember(workspace_id=uuid.uuid4(), user_id=uuid.uuid4(), role="owner")
    assert m.is_privileged() is True


def test_workspace_member_is_privileged_admin():
    m = WorkspaceMember(workspace_id=uuid.uuid4(), user_id=uuid.uuid4(), role="admin")
    assert m.is_privileged() is True


def test_workspace_member_is_privileged_member():
    m = WorkspaceMember(workspace_id=uuid.uuid4(), user_id=uuid.uuid4(), role="member")
    assert m.is_privileged() is False
