"""Verify Organization/Workspace models are importable and column names are correct."""

from app.db.models import Organization, User, Workspace


def test_organization_model_has_required_columns():
    cols = {c.name for c in Organization.__table__.columns}
    assert "id" in cols
    assert "name" in cols
    assert "slug" in cols
    assert "owner_id" in cols
    assert "created_at" in cols


def test_workspace_model_has_required_columns():
    cols = {c.name for c in Workspace.__table__.columns}
    assert "id" in cols
    assert "name" in cols
    assert "organization_id" in cols
    assert "created_at" in cols


def test_user_has_organization_id_column():
    cols = {c.name for c in User.__table__.columns}
    assert "organization_id" in cols


def test_existing_tables_have_workspace_id():
    from app.db.models import Conversation, CronJob, Document, Webhook

    for model in (Conversation, CronJob, Document, Webhook):
        cols = {c.name for c in model.__table__.columns}
        assert "workspace_id" in cols, f"{model.__tablename__} missing workspace_id"
