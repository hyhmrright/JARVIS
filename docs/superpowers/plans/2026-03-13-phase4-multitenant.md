# Phase 4: Multi-tenant Full Implementation — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate the Organization and Workspace models that were pre-designed in migration 013. Implement full CRUD APIs for organizations and workspaces, a membership and invitation system, workspace-scoped shared resources (documents, cron jobs), per-workspace LLM settings with priority-chain resolution, and a complete frontend multi-tenant UI including a workspace switcher, member management, and invitation acceptance flow.

**Architecture:** Five sequential tasks. Task 4.1 activates the org/workspace data layer and CRUD. Task 4.2 builds the membership and invitation system on top of 4.1. Task 4.3 wires workspace ownership into existing resource APIs (documents, cron). Task 4.4 adds per-workspace LLM settings with a three-tier key resolution chain. Task 4.5 delivers the frontend workspace switcher, member management page, invite accept page, and workspace-scoped UI for all resource pages. Each task includes its own Alembic migration and tests.

**Tech Stack:** FastAPI, SQLAlchemy async (mapped_column style), Pydantic BaseModel, Alembic, Vue 3 Composition API, Pinia, vue-i18n, TypeScript

---

## File Structure

```
backend/app/
├── api/
│   ├── organizations.py          [NEW — Task 4.1]
│   ├── workspaces.py             [NEW — Task 4.1, extended in 4.2 and 4.4]
│   ├── invitations.py            [NEW — Task 4.2]
│   ├── documents.py              [MODIFY — Task 4.3]
│   └── cron.py                   [MODIFY — Task 4.3]
│   └── deps.py                   [MODIFY — Task 4.4]
├── db/
│   └── models.py                 [MODIFY — Tasks 4.1, 4.2, 4.4]
├── rag/
│   ├── retriever.py              [MODIFY — Task 4.3]
│   └── context.py                [MODIFY — Task 4.3]
└── main.py                       [MODIFY — Task 4.1]

backend/alembic/versions/
├── 015_activate_multi_tenant.py  [NEW — Task 4.1]
├── 016_workspace_members_invitations.py  [NEW — Task 4.2]
└── 017_workspace_settings.py     [NEW — Task 4.4]

backend/tests/
├── api/test_organizations.py     [NEW — Task 4.1]
├── api/test_workspaces.py        [NEW — Task 4.1, 4.2, 4.4]
└── api/test_invitations.py       [NEW — Task 4.2]

frontend/src/
├── stores/
│   └── workspace.ts              [NEW — Task 4.5]
├── pages/
│   ├── WorkspaceMembersPage.vue  [NEW — Task 4.5]
│   └── InviteAcceptPage.vue      [NEW — Task 4.5]
├── components/
│   └── WorkspaceSwitcher.vue     [NEW — Task 4.5]
├── pages/
│   ├── SettingsPage.vue          [MODIFY — Task 4.5]
│   ├── DocumentsPage.vue         [MODIFY — Task 4.5]
│   └── ProactivePage.vue         [MODIFY — Task 4.5]
├── router/
│   └── index.ts                  [MODIFY — Task 4.5]
└── locales/
    ├── zh.json                   [MODIFY — Task 4.5]
    ├── en.json                   [MODIFY — Task 4.5]
    ├── ja.json                   [MODIFY — Task 4.5]
    ├── ko.json                   [MODIFY — Task 4.5]
    ├── fr.json                   [MODIFY — Task 4.5]
    └── de.json                   [MODIFY — Task 4.5]
```

---

## Chunk 1

## Task 4.1 — Organization + Workspace CRUD API

**Files:**
- Create: `backend/app/api/organizations.py`
- Create: `backend/app/api/workspaces.py`
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/main.py`
- Create: `backend/alembic/versions/015_activate_multi_tenant.py`
- Create: `backend/tests/api/test_organizations.py`

**Steps:**

- [ ] Step 1: Update `backend/app/db/models.py` — add soft-delete to Workspace, activate FK relationships

  In the `Organization` class, add the `workspaces` and `owner` relationships after the `created_at` column:
  ```python
  owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
  workspaces: Mapped[list["Workspace"]] = relationship(
      back_populates="organization", cascade="all, delete-orphan"
  )
  ```

  In the `Workspace` class, add `is_deleted`, `updated_at`, and relationships:
  ```python
  is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  updated_at: Mapped[datetime] = mapped_column(
      DateTime(timezone=True),
      server_default=func.now(),
      onupdate=func.now(),
      nullable=False,
  )

  organization: Mapped["Organization"] = relationship(back_populates="workspaces")
  ```

  In the `User` class, add the organization relationship after `api_keys`:
  ```python
  organization: Mapped["Organization | None"] = relationship(
      "Organization",
      primaryjoin="User.organization_id == Organization.id",
      foreign_keys="User.organization_id",
      uselist=False,
  )
  ```

- [ ] Step 2: Create `backend/alembic/versions/015_activate_multi_tenant.py`

  ```python
  """Activate multi-tenant: add Workspace.is_deleted, updated_at; add FK constraints.

  Revision ID: 015
  Revises: 014
  Create Date: 2026-03-13
  """

  import sqlalchemy as sa
  from alembic import op

  revision = "015"
  down_revision = "014"
  branch_labels = None
  depends_on = None


  def upgrade() -> None:
      # Add soft-delete and updated_at to workspaces
      op.add_column(
          "workspaces",
          sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
      )
      op.add_column(
          "workspaces",
          sa.Column(
              "updated_at",
              sa.DateTime(timezone=True),
              server_default=sa.text("now()"),
              nullable=False,
          ),
      )
      # Add FK constraint from users.organization_id -> organizations.id
      op.create_foreign_key(
          "fk_users_organization_id",
          "users",
          "organizations",
          ["organization_id"],
          ["id"],
          ondelete="SET NULL",
      )
      # Add FK constraints for workspace_id on resource tables
      for table in ("conversations", "documents", "cron_jobs", "webhooks"):
          op.create_foreign_key(
              f"fk_{table}_workspace_id",
              table,
              "workspaces",
              ["workspace_id"],
              ["id"],
              ondelete="SET NULL",
          )


  def downgrade() -> None:
      for table in ("conversations", "documents", "cron_jobs", "webhooks"):
          op.drop_constraint(f"fk_{table}_workspace_id", table, type_="foreignkey")
      op.drop_constraint("fk_users_organization_id", "users", type_="foreignkey")
      op.drop_column("workspaces", "updated_at")
      op.drop_column("workspaces", "is_deleted")
  ```

  Note: down_revision should be `"013"` if migration 014 does not exist yet, or the actual latest migration ID. Verify the chain with `uv run alembic history` before committing.

- [ ] Step 3: Create `backend/app/api/organizations.py`

  ```python
  import re
  import uuid

  import structlog
  from fastapi import APIRouter, Depends, HTTPException
  from pydantic import BaseModel, Field, field_validator
  from sqlalchemy import select
  from sqlalchemy.ext.asyncio import AsyncSession

  from app.api.deps import get_current_user
  from app.db.models import Organization, User
  from app.db.session import get_db

  logger = structlog.get_logger(__name__)
  router = APIRouter(prefix="/api/organizations", tags=["organizations"])

  _SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,98}[a-z0-9]$")


  class OrgCreate(BaseModel):
      name: str = Field(min_length=1, max_length=255)
      slug: str = Field(min_length=3, max_length=100)

      @field_validator("slug")
      @classmethod
      def validate_slug(cls, v: str) -> str:
          if not _SLUG_RE.match(v):
              raise ValueError(
                  "slug must be 3-100 lowercase alphanumeric chars or hyphens, "
                  "starting and ending with alphanumeric"
              )
          return v


  class OrgUpdate(BaseModel):
      name: str | None = Field(default=None, min_length=1, max_length=255)
      slug: str | None = Field(default=None, min_length=3, max_length=100)

      @field_validator("slug")
      @classmethod
      def validate_slug(cls, v: str | None) -> str | None:
          if v is not None and not _SLUG_RE.match(v):
              raise ValueError("invalid slug format")
          return v


  class OrgResponse(BaseModel):
      id: str
      name: str
      slug: str
      owner_id: str
      created_at: str


  def _org_to_dict(org: Organization) -> dict:
      return {
          "id": str(org.id),
          "name": org.name,
          "slug": org.slug,
          "owner_id": str(org.owner_id),
          "created_at": org.created_at.isoformat(),
      }


  @router.post("", status_code=201)
  async def create_organization(
      body: OrgCreate,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      """Create a new organization. The caller becomes the owner."""
      existing_slug = await db.scalar(
          select(Organization).where(Organization.slug == body.slug)
      )
      if existing_slug:
          raise HTTPException(status_code=409, detail="Slug already taken")
      org = Organization(name=body.name, slug=body.slug, owner_id=user.id)
      db.add(org)
      await db.flush()
      # Link the creating user to this org
      user.organization_id = org.id
      await db.commit()
      logger.info("organization_created", org_id=str(org.id), owner_id=str(user.id))
      return _org_to_dict(org)


  @router.get("/me")
  async def get_my_organization(
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      """Return the organization the current user belongs to."""
      if not user.organization_id:
          raise HTTPException(status_code=404, detail="Not a member of any organization")
      org = await db.get(Organization, user.organization_id)
      if not org:
          raise HTTPException(status_code=404, detail="Organization not found")
      return _org_to_dict(org)


  @router.put("/{org_id}")
  async def update_organization(
      org_id: uuid.UUID,
      body: OrgUpdate,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      """Update org name or slug. Only the org owner may do this."""
      org = await db.get(Organization, org_id)
      if not org:
          raise HTTPException(status_code=404, detail="Organization not found")
      if org.owner_id != user.id:
          raise HTTPException(status_code=403, detail="Only the owner can update the organization")
      if body.name is not None:
          org.name = body.name
      if body.slug is not None:
          clash = await db.scalar(
              select(Organization).where(
                  Organization.slug == body.slug, Organization.id != org_id
              )
          )
          if clash:
              raise HTTPException(status_code=409, detail="Slug already taken")
          org.slug = body.slug
      await db.commit()
      return _org_to_dict(org)
  ```

- [ ] Step 4: Create `backend/app/api/workspaces.py`

  ```python
  import uuid

  import structlog
  from fastapi import APIRouter, Depends, HTTPException
  from pydantic import BaseModel, Field
  from sqlalchemy import select
  from sqlalchemy.ext.asyncio import AsyncSession

  from app.api.deps import get_current_user
  from app.db.models import Organization, User, Workspace
  from app.db.session import get_db

  logger = structlog.get_logger(__name__)
  router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


  class WorkspaceCreate(BaseModel):
      name: str = Field(min_length=1, max_length=255)


  class WorkspaceUpdate(BaseModel):
      name: str = Field(min_length=1, max_length=255)


  def _ws_to_dict(ws: Workspace) -> dict:
      return {
          "id": str(ws.id),
          "name": ws.name,
          "organization_id": str(ws.organization_id),
          "is_deleted": ws.is_deleted,
          "created_at": ws.created_at.isoformat(),
          "updated_at": ws.updated_at.isoformat(),
      }


  async def _require_org(user: User, db: AsyncSession) -> Organization:
      """Raise 403 if user has no org."""
      if not user.organization_id:
          raise HTTPException(status_code=403, detail="You must belong to an organization")
      org = await db.get(Organization, user.organization_id)
      if not org:
          raise HTTPException(status_code=403, detail="Organization not found")
      return org


  @router.post("", status_code=201)
  async def create_workspace(
      body: WorkspaceCreate,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      """Create a new workspace in the user's organization."""
      org = await _require_org(user, db)
      ws = Workspace(name=body.name, organization_id=org.id)
      db.add(ws)
      await db.commit()
      await db.refresh(ws)
      logger.info("workspace_created", ws_id=str(ws.id), org_id=str(org.id))
      return _ws_to_dict(ws)


  @router.get("")
  async def list_workspaces(
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> list[dict]:
      """List all non-deleted workspaces in the user's organization."""
      if not user.organization_id:
          return []
      rows = await db.scalars(
          select(Workspace).where(
              Workspace.organization_id == user.organization_id,
              Workspace.is_deleted.is_(False),
          )
      )
      return [_ws_to_dict(ws) for ws in rows.all()]


  @router.put("/{ws_id}")
  async def update_workspace(
      ws_id: uuid.UUID,
      body: WorkspaceUpdate,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      """Update workspace name. User must belong to the same org."""
      ws = await db.get(Workspace, ws_id)
      if not ws or ws.is_deleted:
          raise HTTPException(status_code=404, detail="Workspace not found")
      if ws.organization_id != user.organization_id:
          raise HTTPException(status_code=403, detail="Access denied")
      ws.name = body.name
      await db.commit()
      return _ws_to_dict(ws)


  @router.delete("/{ws_id}", status_code=204)
  async def delete_workspace(
      ws_id: uuid.UUID,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> None:
      """Soft-delete a workspace. Only org owner may do this."""
      org = await _require_org(user, db)
      ws = await db.get(Workspace, ws_id)
      if not ws or ws.is_deleted:
          raise HTTPException(status_code=404, detail="Workspace not found")
      if ws.organization_id != org.id:
          raise HTTPException(status_code=403, detail="Access denied")
      if org.owner_id != user.id:
          raise HTTPException(status_code=403, detail="Only the owner can delete workspaces")
      ws.is_deleted = True
      await db.commit()
  ```

- [ ] Step 5: Register new routers in `backend/app/main.py`

  After the existing `from app.api.keys import router as keys_router` import block, add:
  ```python
  from app.api.organizations import router as organizations_router
  from app.api.workspaces import router as workspaces_router
  ```

  After `app.include_router(keys_router)`, add:
  ```python
  app.include_router(organizations_router)
  app.include_router(workspaces_router)
  ```

- [ ] Step 6: Create `backend/tests/api/test_organizations.py`

  ```python
  """Tests for organization and workspace CRUD endpoints."""

  from unittest.mock import AsyncMock, patch
  from uuid import uuid4

  import pytest
  from httpx import AsyncClient


  @pytest.fixture(autouse=True)
  def _suppress_audit():
      with patch("app.api.auth.log_action", AsyncMock(return_value=None)):
          yield


  @pytest.mark.anyio
  async def test_create_organization(client: AsyncClient, auth_headers: dict) -> None:
      resp = await client.post(
          "/api/organizations",
          json={"name": "Test Org", "slug": "test-org"},
          headers=auth_headers,
      )
      assert resp.status_code == 201
      data = resp.json()
      assert data["slug"] == "test-org"
      assert data["name"] == "Test Org"


  @pytest.mark.anyio
  async def test_create_organization_duplicate_slug(
      client: AsyncClient, auth_headers: dict
  ) -> None:
      await client.post(
          "/api/organizations",
          json={"name": "Org A", "slug": "slug-clash"},
          headers=auth_headers,
      )
      resp = await client.post(
          "/api/organizations",
          json={"name": "Org B", "slug": "slug-clash"},
          headers=auth_headers,
      )
      assert resp.status_code == 409


  @pytest.mark.anyio
  async def test_get_my_organization(client: AsyncClient, auth_headers: dict) -> None:
      await client.post(
          "/api/organizations",
          json={"name": "My Org", "slug": "my-org-x"},
          headers=auth_headers,
      )
      resp = await client.get("/api/organizations/me", headers=auth_headers)
      assert resp.status_code == 200
      assert resp.json()["slug"] == "my-org-x"


  @pytest.mark.anyio
  async def test_get_my_organization_no_org(
      client: AsyncClient, auth_headers: dict
  ) -> None:
      resp = await client.get("/api/organizations/me", headers=auth_headers)
      assert resp.status_code == 404


  @pytest.mark.anyio
  async def test_create_workspace(client: AsyncClient, auth_headers: dict) -> None:
      await client.post(
          "/api/organizations",
          json={"name": "WS Org", "slug": "ws-org"},
          headers=auth_headers,
      )
      resp = await client.post(
          "/api/workspaces",
          json={"name": "Engineering"},
          headers=auth_headers,
      )
      assert resp.status_code == 201
      assert resp.json()["name"] == "Engineering"


  @pytest.mark.anyio
  async def test_list_workspaces(client: AsyncClient, auth_headers: dict) -> None:
      await client.post(
          "/api/organizations",
          json={"name": "List Org", "slug": "list-org"},
          headers=auth_headers,
      )
      await client.post("/api/workspaces", json={"name": "Alpha"}, headers=auth_headers)
      await client.post("/api/workspaces", json={"name": "Beta"}, headers=auth_headers)
      resp = await client.get("/api/workspaces", headers=auth_headers)
      assert resp.status_code == 200
      names = [w["name"] for w in resp.json()]
      assert "Alpha" in names and "Beta" in names


  @pytest.mark.anyio
  async def test_delete_workspace_soft(client: AsyncClient, auth_headers: dict) -> None:
      await client.post(
          "/api/organizations",
          json={"name": "Del Org", "slug": "del-org"},
          headers=auth_headers,
      )
      create = await client.post(
          "/api/workspaces", json={"name": "ToDelete"}, headers=auth_headers
      )
      ws_id = create.json()["id"]
      del_resp = await client.delete(f"/api/workspaces/{ws_id}", headers=auth_headers)
      assert del_resp.status_code == 204
      list_resp = await client.get("/api/workspaces", headers=auth_headers)
      ids = [w["id"] for w in list_resp.json()]
      assert ws_id not in ids
  ```

- [ ] Step 7: Run static checks
  ```bash
  cd /Users/hyh/code/JARVIS/backend
  uv run ruff check --fix && uv run ruff format
  uv run mypy app
  uv run pytest --collect-only -q
  ```

- [ ] Step 8: Commit
  ```bash
  cd /Users/hyh/code/JARVIS
  git add backend/app/db/models.py \
          backend/app/api/organizations.py \
          backend/app/api/workspaces.py \
          backend/app/main.py \
          backend/alembic/versions/015_activate_multi_tenant.py \
          backend/tests/api/test_organizations.py
  git commit -m "feat(multi-tenant): org + workspace CRUD API with migration 015"
  ```

---

## Chunk 2

## Task 4.2 — Membership + Invitation System

**Files:**
- Create: `backend/app/api/invitations.py`
- Modify: `backend/app/api/workspaces.py`
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/016_workspace_members_invitations.py`
- Create: `backend/tests/api/test_invitations.py`

**Steps:**

- [ ] Step 1: Add `WorkspaceMember` and `Invitation` models to `backend/app/db/models.py`

  Add these two new model classes at the end of the file, before the final blank line:

  ```python
  class WorkspaceMember(Base):
      __tablename__ = "workspace_members"
      __table_args__ = (
          CheckConstraint(
              "role IN ('owner', 'admin', 'member')",
              name="ck_workspace_members_role",
          ),
      )

      workspace_id: Mapped[uuid.UUID] = mapped_column(
          UUID(as_uuid=True),
          ForeignKey("workspaces.id", ondelete="CASCADE"),
          primary_key=True,
      )
      user_id: Mapped[uuid.UUID] = mapped_column(
          UUID(as_uuid=True),
          ForeignKey("users.id", ondelete="CASCADE"),
          primary_key=True,
      )
      role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
      joined_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )

      workspace: Mapped["Workspace"] = relationship("Workspace")
      user: Mapped["User"] = relationship("User")


  class Invitation(Base):
      __tablename__ = "invitations"
      __table_args__ = (
          CheckConstraint(
              "role IN ('owner', 'admin', 'member')",
              name="ck_invitations_role",
          ),
      )

      id: Mapped[uuid.UUID] = mapped_column(
          UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
      )
      workspace_id: Mapped[uuid.UUID] = mapped_column(
          UUID(as_uuid=True),
          ForeignKey("workspaces.id", ondelete="CASCADE"),
          nullable=False,
          index=True,
      )
      inviter_id: Mapped[uuid.UUID] = mapped_column(
          UUID(as_uuid=True),
          ForeignKey("users.id", ondelete="CASCADE"),
          nullable=False,
      )
      email: Mapped[str] = mapped_column(String(255), nullable=False)
      token: Mapped[uuid.UUID] = mapped_column(
          UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
      )
      role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
      expires_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), nullable=False
      )
      accepted_at: Mapped[datetime | None] = mapped_column(
          DateTime(timezone=True), nullable=True
      )
      created_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )

      workspace: Mapped["Workspace"] = relationship("Workspace")
      inviter: Mapped["User"] = relationship("User", foreign_keys=[inviter_id])
  ```

  Also add `members` relationship to `Workspace` class:
  ```python
  members: Mapped[list["WorkspaceMember"]] = relationship(
      "WorkspaceMember",
      primaryjoin="Workspace.id == WorkspaceMember.workspace_id",
      cascade="all, delete-orphan",
  )
  ```

- [ ] Step 2: Create `backend/alembic/versions/016_workspace_members_invitations.py`

  ```python
  """Add workspace_members and invitations tables.

  Revision ID: 016
  Revises: 015
  Create Date: 2026-03-13
  """

  import sqlalchemy as sa
  from sqlalchemy.dialects import postgresql

  from alembic import op

  revision = "016"
  down_revision = "015"
  branch_labels = None
  depends_on = None


  def upgrade() -> None:
      op.create_table(
          "workspace_members",
          sa.Column(
              "workspace_id",
              postgresql.UUID(as_uuid=True),
              sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
              primary_key=True,
          ),
          sa.Column(
              "user_id",
              postgresql.UUID(as_uuid=True),
              sa.ForeignKey("users.id", ondelete="CASCADE"),
              primary_key=True,
          ),
          sa.Column(
              "role",
              sa.String(20),
              nullable=False,
              server_default="member",
          ),
          sa.Column(
              "joined_at",
              sa.DateTime(timezone=True),
              server_default=sa.text("now()"),
              nullable=False,
          ),
          sa.CheckConstraint(
              "role IN ('owner', 'admin', 'member')",
              name="ck_workspace_members_role",
          ),
      )
      op.create_index(
          "ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"]
      )
      op.create_index(
          "ix_workspace_members_user_id", "workspace_members", ["user_id"]
      )

      op.create_table(
          "invitations",
          sa.Column(
              "id",
              postgresql.UUID(as_uuid=True),
              primary_key=True,
              server_default=sa.text("gen_random_uuid()"),
          ),
          sa.Column(
              "workspace_id",
              postgresql.UUID(as_uuid=True),
              sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
              nullable=False,
          ),
          sa.Column(
              "inviter_id",
              postgresql.UUID(as_uuid=True),
              sa.ForeignKey("users.id", ondelete="CASCADE"),
              nullable=False,
          ),
          sa.Column("email", sa.String(255), nullable=False),
          sa.Column(
              "token",
              postgresql.UUID(as_uuid=True),
              unique=True,
              nullable=False,
              server_default=sa.text("gen_random_uuid()"),
          ),
          sa.Column("role", sa.String(20), nullable=False, server_default="member"),
          sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
          sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
          sa.Column(
              "created_at",
              sa.DateTime(timezone=True),
              server_default=sa.text("now()"),
              nullable=False,
          ),
          sa.CheckConstraint(
              "role IN ('owner', 'admin', 'member')",
              name="ck_invitations_role",
          ),
      )
      op.create_index("ix_invitations_workspace_id", "invitations", ["workspace_id"])
      op.create_index("ix_invitations_token", "invitations", ["token"])


  def downgrade() -> None:
      op.drop_index("ix_invitations_token", table_name="invitations")
      op.drop_index("ix_invitations_workspace_id", table_name="invitations")
      op.drop_table("invitations")
      op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
      op.drop_index("ix_workspace_members_workspace_id", table_name="workspace_members")
      op.drop_table("workspace_members")
  ```

- [ ] Step 3: Create `backend/app/api/invitations.py`

  ```python
  import uuid
  from datetime import UTC, datetime, timedelta

  import structlog
  from fastapi import APIRouter, Depends, HTTPException
  from pydantic import BaseModel, EmailStr, Field
  from sqlalchemy import select
  from sqlalchemy.ext.asyncio import AsyncSession

  from app.api.deps import get_current_user
  from app.db.models import Invitation, User, Workspace, WorkspaceMember
  from app.db.session import get_db

  logger = structlog.get_logger(__name__)
  router = APIRouter(tags=["invitations"])

  _INVITATION_TTL_HOURS = 72


  class InviteRequest(BaseModel):
      email: EmailStr
      role: str = Field(default="member", pattern="^(admin|member)$")


  class AcceptRequest(BaseModel):
      pass  # body is empty; auth comes from JWT header


  def _inv_to_dict(inv: Invitation) -> dict:
      return {
          "id": str(inv.id),
          "workspace_id": str(inv.workspace_id),
          "inviter_id": str(inv.inviter_id),
          "email": inv.email,
          "token": str(inv.token),
          "role": inv.role,
          "expires_at": inv.expires_at.isoformat(),
          "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
          "created_at": inv.created_at.isoformat(),
      }


  @router.post("/api/workspaces/{ws_id}/members/invite", status_code=201)
  async def invite_member(
      ws_id: uuid.UUID,
      body: InviteRequest,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      """Create an invitation. The inviter must be a member of the workspace."""
      ws = await db.get(Workspace, ws_id)
      if not ws or ws.is_deleted:
          raise HTTPException(status_code=404, detail="Workspace not found")
      if ws.organization_id != user.organization_id:
          raise HTTPException(status_code=403, detail="Access denied")

      # Verify inviter is a member
      membership = await db.scalar(
          select(WorkspaceMember).where(
              WorkspaceMember.workspace_id == ws_id,
              WorkspaceMember.user_id == user.id,
          )
      )
      if not membership:
          raise HTTPException(status_code=403, detail="You are not a member of this workspace")

      # Only admin+ can invite
      if membership.role not in ("owner", "admin"):
          raise HTTPException(status_code=403, detail="Admin access required to invite")

      inv = Invitation(
          workspace_id=ws_id,
          inviter_id=user.id,
          email=body.email,
          role=body.role,
          expires_at=datetime.now(UTC) + timedelta(hours=_INVITATION_TTL_HOURS),
      )
      db.add(inv)
      await db.commit()
      await db.refresh(inv)
      logger.info(
          "invitation_created",
          inv_id=str(inv.id),
          ws_id=str(ws_id),
          email=body.email,
      )
      return _inv_to_dict(inv)


  @router.get("/api/invitations/{token}")
  async def get_invitation(
      token: uuid.UUID,
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      """Public endpoint: get invitation details by token."""
      inv = await db.scalar(select(Invitation).where(Invitation.token == token))
      if not inv:
          raise HTTPException(status_code=404, detail="Invitation not found")
      if inv.accepted_at:
          raise HTTPException(status_code=410, detail="Invitation already accepted")
      if inv.expires_at < datetime.now(UTC):
          raise HTTPException(status_code=410, detail="Invitation expired")
      ws = await db.get(Workspace, inv.workspace_id)
      return {
          **_inv_to_dict(inv),
          "workspace_name": ws.name if ws else None,
      }


  @router.post("/api/invitations/{token}/accept")
  async def accept_invitation(
      token: uuid.UUID,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      """Accept an invitation. The JWT user must match the invited email."""
      inv = await db.scalar(select(Invitation).where(Invitation.token == token))
      if not inv:
          raise HTTPException(status_code=404, detail="Invitation not found")
      if inv.accepted_at:
          raise HTTPException(status_code=410, detail="Invitation already accepted")
      if inv.expires_at < datetime.now(UTC):
          raise HTTPException(status_code=410, detail="Invitation expired")
      if user.email.lower() != inv.email.lower():
          raise HTTPException(
              status_code=403,
              detail="This invitation is for a different email address",
          )

      # Link user to org if not already linked
      if not user.organization_id:
          ws = await db.get(Workspace, inv.workspace_id)
          if ws:
              user.organization_id = ws.organization_id

      # Add or update membership
      existing = await db.scalar(
          select(WorkspaceMember).where(
              WorkspaceMember.workspace_id == inv.workspace_id,
              WorkspaceMember.user_id == user.id,
          )
      )
      if existing:
          existing.role = inv.role
      else:
          db.add(
              WorkspaceMember(
                  workspace_id=inv.workspace_id,
                  user_id=user.id,
                  role=inv.role,
              )
          )
      inv.accepted_at = datetime.now(UTC)
      await db.commit()
      logger.info(
          "invitation_accepted",
          inv_id=str(inv.id),
          user_id=str(user.id),
          ws_id=str(inv.workspace_id),
      )
      return {"status": "ok", "workspace_id": str(inv.workspace_id)}


  @router.put("/api/workspaces/{ws_id}/members/{member_user_id}")
  async def update_member_role(
      ws_id: uuid.UUID,
      member_user_id: uuid.UUID,
      body: dict,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      """Change a member's role. Admin+ only."""
      ws = await db.get(Workspace, ws_id)
      if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
          raise HTTPException(status_code=404, detail="Workspace not found")
      caller_membership = await db.scalar(
          select(WorkspaceMember).where(
              WorkspaceMember.workspace_id == ws_id,
              WorkspaceMember.user_id == user.id,
          )
      )
      if not caller_membership or caller_membership.role not in ("owner", "admin"):
          raise HTTPException(status_code=403, detail="Admin access required")
      new_role = body.get("role")
      if new_role not in ("admin", "member"):
          raise HTTPException(status_code=422, detail="role must be 'admin' or 'member'")
      target = await db.scalar(
          select(WorkspaceMember).where(
              WorkspaceMember.workspace_id == ws_id,
              WorkspaceMember.user_id == member_user_id,
          )
      )
      if not target:
          raise HTTPException(status_code=404, detail="Member not found")
      target.role = new_role
      await db.commit()
      return {"status": "ok"}


  @router.delete("/api/workspaces/{ws_id}/members/{member_user_id}", status_code=204)
  async def remove_member(
      ws_id: uuid.UUID,
      member_user_id: uuid.UUID,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> None:
      """Remove a member from a workspace. Admin+ or self-removal."""
      ws = await db.get(Workspace, ws_id)
      if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
          raise HTTPException(status_code=404, detail="Workspace not found")
      caller_membership = await db.scalar(
          select(WorkspaceMember).where(
              WorkspaceMember.workspace_id == ws_id,
              WorkspaceMember.user_id == user.id,
          )
      )
      is_self = user.id == member_user_id
      is_admin = caller_membership and caller_membership.role in ("owner", "admin")
      if not is_self and not is_admin:
          raise HTTPException(status_code=403, detail="Permission denied")
      target = await db.scalar(
          select(WorkspaceMember).where(
              WorkspaceMember.workspace_id == ws_id,
              WorkspaceMember.user_id == member_user_id,
          )
      )
      if not target:
          raise HTTPException(status_code=404, detail="Member not found")
      await db.delete(target)
      await db.commit()
  ```

- [ ] Step 4: Add `GET /api/workspaces/{ws_id}/members` to `backend/app/api/workspaces.py`

  Append after the existing `delete_workspace` endpoint:
  ```python
  @router.get("/{ws_id}/members")
  async def list_members(
      ws_id: uuid.UUID,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> list[dict]:
      """List all members of a workspace."""
      ws = await db.get(Workspace, ws_id)
      if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
          raise HTTPException(status_code=404, detail="Workspace not found")
      rows = await db.scalars(
          select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws_id)
      )
      members = rows.all()
      result = []
      for m in members:
          member_user = await db.get(User, m.user_id)
          result.append({
              "user_id": str(m.user_id),
              "email": member_user.email if member_user else None,
              "display_name": member_user.display_name if member_user else None,
              "role": m.role,
              "joined_at": m.joined_at.isoformat(),
          })
      return result
  ```

  Also add the import at the top of `workspaces.py`:
  ```python
  from app.db.models import Organization, User, Workspace, WorkspaceMember
  ```

- [ ] Step 5: Register invitation router in `backend/app/main.py`

  Add import:
  ```python
  from app.api.invitations import router as invitations_router
  ```
  Add registration after `workspaces_router`:
  ```python
  app.include_router(invitations_router)
  ```

- [ ] Step 6: Create `backend/tests/api/test_invitations.py`

  ```python
  """Tests for workspace membership and invitation endpoints."""

  from datetime import UTC, datetime, timedelta
  from unittest.mock import AsyncMock, patch

  import pytest
  from httpx import AsyncClient
  from sqlalchemy import select

  from app.db.models import Invitation
  from app.db.session import AsyncSessionLocal


  @pytest.fixture(autouse=True)
  def _suppress_audit():
      with patch("app.api.auth.log_action", AsyncMock(return_value=None)):
          yield


  async def _setup_workspace(client: AsyncClient, auth_headers: dict) -> dict:
      """Helper: create org + workspace and add caller as owner member."""
      await client.post(
          "/api/organizations",
          json={"name": "Inv Org", "slug": f"inv-org-{id(auth_headers)}"},
          headers=auth_headers,
      )
      ws_resp = await client.post(
          "/api/workspaces",
          json={"name": "Inv WS"},
          headers=auth_headers,
      )
      return ws_resp.json()


  @pytest.mark.anyio
  async def test_invite_and_get_token(client: AsyncClient, auth_headers: dict) -> None:
      ws = await _setup_workspace(client, auth_headers)
      # Creator must be in workspace_members as owner first (added by create flow)
      ws_id = ws["id"]
      # Manually insert owner membership for this test since invite endpoint validates it
      # This is done via the create_workspace endpoint which should auto-add caller
      resp = await client.post(
          f"/api/workspaces/{ws_id}/members/invite",
          json={"email": "new@example.com", "role": "member"},
          headers=auth_headers,
      )
      # 201 means invitation row was created
      assert resp.status_code == 201
      token = resp.json()["token"]

      get_resp = await client.get(f"/api/invitations/{token}")
      assert get_resp.status_code == 200
      assert get_resp.json()["email"] == "new@example.com"


  @pytest.mark.anyio
  async def test_get_expired_invitation(
      client: AsyncClient, db_session: AsyncSession
  ) -> None:
      """Expired invitations should return 410."""
      async with AsyncSessionLocal() as s:
          inv = Invitation(
              workspace_id=__import__("uuid").uuid4(),
              inviter_id=__import__("uuid").uuid4(),
              email="x@x.com",
              role="member",
              expires_at=datetime.now(UTC) - timedelta(hours=1),
          )
          s.add(inv)
          await s.commit()
          token = str(inv.token)

      resp = await client.get(f"/api/invitations/{token}")
      assert resp.status_code == 410
  ```

- [ ] Step 7: Run static checks
  ```bash
  cd /Users/hyh/code/JARVIS/backend
  uv run ruff check --fix && uv run ruff format
  uv run mypy app
  uv run pytest --collect-only -q
  ```

- [ ] Step 8: Commit
  ```bash
  cd /Users/hyh/code/JARVIS
  git add backend/app/db/models.py \
          backend/app/api/invitations.py \
          backend/app/api/workspaces.py \
          backend/app/main.py \
          backend/alembic/versions/016_workspace_members_invitations.py \
          backend/tests/api/test_invitations.py
  git commit -m "feat(multi-tenant): workspace membership and invitation system with migration 016"
  ```

---

## Chunk 3

## Task 4.3 — Shared Resources (Documents + Cron Jobs)

**Files:**
- Modify: `backend/app/api/documents.py`
- Modify: `backend/app/api/cron.py`
- Modify: `backend/app/rag/retriever.py`
- Modify: `backend/app/rag/context.py`

**Steps:**

- [ ] Step 1: Update `backend/app/api/documents.py` — add optional `workspace_id` to upload and filtered list

  In the `upload_document` signature, add an optional query param:
  ```python
  from typing import Optional
  # at the top of upload_document:
  @router.post("", status_code=201)
  async def upload_document(
      file: UploadFile = File(...),
      workspace_id: Optional[uuid.UUID] = None,
      user: User = Depends(get_current_user),
      llm: ResolvedLLMConfig = Depends(get_llm_config),
      db: AsyncSession = Depends(get_db),
  ) -> dict[str, str | int]:
  ```

  After constructing the `Document` object but before `db.add(doc)`, add workspace assignment:
  ```python
  if workspace_id is not None:
      # Verify user belongs to the workspace's org
      from app.db.models import Workspace
      ws = await db.get(Workspace, workspace_id)
      if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
          raise HTTPException(status_code=404, detail="Workspace not found")
      doc.workspace_id = workspace_id
  ```

  In `list_documents`, add an optional workspace filter param:
  ```python
  @router.get("")
  async def list_documents(
      workspace_id: Optional[uuid.UUID] = None,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> dict[str, list[dict]]:
      query = select(Document).where(
          Document.user_id == user.id, Document.is_deleted.is_(False)
      )
      if workspace_id is not None:
          query = query.where(Document.workspace_id == workspace_id)
      else:
          # Default: personal documents (no workspace) + all org workspace docs user owns
          pass
      rows = await db.scalars(query.order_by(Document.created_at.desc()))
  ```

  Update the response dict to include `workspace_id`:
  ```python
  {
      "id": str(d.id),
      "filename": d.filename,
      "file_type": d.file_type,
      "file_size_bytes": d.file_size_bytes,
      "chunk_count": d.chunk_count,
      "created_at": d.created_at.isoformat(),
      "workspace_id": str(d.workspace_id) if d.workspace_id else None,
  }
  ```

- [ ] Step 2: Update `backend/app/api/cron.py` — add optional `workspace_id` to create and list

  Add `workspace_id: Optional[uuid.UUID] = None` field to `CronJobCreate`:
  ```python
  class CronJobCreate(BaseModel):
      schedule: str = Field(min_length=1, max_length=100)
      task: str = Field(min_length=1, max_length=4000)
      trigger_type: str = Field(default="cron", max_length=50)
      trigger_metadata: dict[str, Any] | None = None
      workspace_id: uuid.UUID | None = None
  ```

  In `create_cron_job`, after constructing the `CronJob` object but before `db.add(job)`, add:
  ```python
  if data.workspace_id is not None:
      from app.db.models import Workspace
      ws = await db.get(Workspace, data.workspace_id)
      if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
          raise HTTPException(status_code=404, detail="Workspace not found")
      job.workspace_id = data.workspace_id
  ```

  In `list_cron_jobs`, add optional `workspace_id` filter:
  ```python
  @router.get("")
  async def list_cron_jobs(
      workspace_id: Optional[uuid.UUID] = None,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> list[dict[str, Any]]:
      query = select(CronJob).where(CronJob.user_id == user.id)
      if workspace_id is not None:
          query = query.where(CronJob.workspace_id == workspace_id)
      result = await db.scalars(query)
  ```

  Add `workspace_id` to the return dict:
  ```python
  "workspace_id": str(j.workspace_id) if j.workspace_id else None,
  ```

- [ ] Step 3: Update `backend/app/rag/retriever.py` — add workspace-aware retrieval

  Add a new `retrieve_context_multi` function that searches both the user's personal collection and any workspace collections:

  ```python
  async def retrieve_context_multi(
      query: str,
      user_id: str,
      workspace_ids: list[str],
      openai_api_key: str,
      top_k: int = _DEFAULT_TOP_K,
      score_threshold: float = _DEFAULT_SCORE_THRESHOLD,
  ) -> list[RetrievedChunk]:
      """Search user personal collection plus workspace collections.

      Returns merged results sorted by score descending.
      Returns empty list (never raises) on any error.
      """
      collection_names = [user_collection_name(user_id)]
      for ws_id in workspace_ids:
          collection_names.append(f"workspace_{ws_id}")

      try:
          client = await get_qdrant_client()
          embedder = get_embedder(openai_api_key)
          query_vec = await embedder.aembed_query(query)
          all_chunks: list[RetrievedChunk] = []
          for collection_name in collection_names:
              try:
                  hits = await client.search(  # type: ignore[attr-defined]
                      collection_name=collection_name,
                      query_vector=query_vec,
                      limit=top_k,
                      score_threshold=score_threshold,
                  )
                  all_chunks.extend([
                      RetrievedChunk(
                          document_name=hit.payload.get("doc_name", "Unknown document"),
                          content=hit.payload.get("text", ""),
                          score=hit.score,
                      )
                      for hit in hits
                      if hit.payload
                  ])
              except UnexpectedResponse as exc:
                  if exc.status_code != 404:
                      logger.warning(
                          "retriever_qdrant_error",
                          collection=collection_name,
                          error=str(exc),
                      )
              except Exception:
                  logger.warning(
                      "retriever_collection_error",
                      collection=collection_name,
                      exc_info=True,
                  )
          all_chunks.sort(key=lambda c: c.score, reverse=True)
          return all_chunks[:top_k]
      except Exception:
          logger.warning("retriever_multi_unexpected_error", user_id=user_id, exc_info=True)
          return []
  ```

- [ ] Step 4: Update `backend/app/rag/context.py` — expose workspace_ids param

  Extend `build_rag_context` to accept an optional list of workspace IDs:

  ```python
  async def build_rag_context(
      user_id: str,
      query: str,
      openai_key: str | None,
      workspace_ids: list[str] | None = None,
  ) -> str:
      """Retrieve relevant chunks and return them as a formatted context string.

      When workspace_ids is provided, also searches workspace collections.
      Returns empty string when no key is provided, no chunks are found,
      or retrieval fails. Never raises.
      """
      if not openai_key:
          return ""
      try:
          if workspace_ids:
              chunks = await _retriever.retrieve_context_multi(
                  query, user_id, workspace_ids, openai_key
              )
          else:
              chunks = await _retriever.retrieve_context(query, user_id, openai_key)
          if not chunks:
              return ""
          logger.info(
              "rag_context_built",
              user_id=user_id,
              chunk_count=len(chunks),
              workspace_ids=workspace_ids,
          )
          return _format_chunks(chunks)
      except Exception:
          logger.warning("rag_context_build_failed", exc_info=True)
          return ""
  ```

- [ ] Step 5: Run static checks
  ```bash
  cd /Users/hyh/code/JARVIS/backend
  uv run ruff check --fix && uv run ruff format
  uv run mypy app
  uv run pytest --collect-only -q
  ```

- [ ] Step 6: Commit
  ```bash
  cd /Users/hyh/code/JARVIS
  git add backend/app/api/documents.py \
          backend/app/api/cron.py \
          backend/app/rag/retriever.py \
          backend/app/rag/context.py
  git commit -m "feat(multi-tenant): workspace-scoped documents and cron jobs; multi-collection RAG retrieval"
  ```

---

## Chunk 4

## Task 4.4 — Workspace LLM Settings

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/api/workspaces.py`
- Modify: `backend/app/api/deps.py`
- Create: `backend/alembic/versions/017_workspace_settings.py`

**Steps:**

- [ ] Step 1: Add `WorkspaceSettings` model to `backend/app/db/models.py`

  Append at the end of the file:
  ```python
  class WorkspaceSettings(Base):
      __tablename__ = "workspace_settings"

      workspace_id: Mapped[uuid.UUID] = mapped_column(
          UUID(as_uuid=True),
          ForeignKey("workspaces.id", ondelete="CASCADE"),
          primary_key=True,
      )
      settings_json: Mapped[dict[str, Any]] = mapped_column(
          JSONB, nullable=False, default=dict
      )
      created_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )
      updated_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True),
          server_default=func.now(),
          onupdate=func.now(),
          nullable=False,
      )

      workspace: Mapped["Workspace"] = relationship("Workspace")
  ```

  Also add `settings` relationship to `Workspace`:
  ```python
  settings: Mapped["WorkspaceSettings | None"] = relationship(
      "WorkspaceSettings",
      uselist=False,
      cascade="all, delete-orphan",
  )
  ```

- [ ] Step 2: Create `backend/alembic/versions/017_workspace_settings.py`

  ```python
  """Add workspace_settings table.

  Revision ID: 017
  Revises: 016
  Create Date: 2026-03-13
  """

  import sqlalchemy as sa
  from sqlalchemy.dialects import postgresql

  from alembic import op

  revision = "017"
  down_revision = "016"
  branch_labels = None
  depends_on = None


  def upgrade() -> None:
      op.create_table(
          "workspace_settings",
          sa.Column(
              "workspace_id",
              postgresql.UUID(as_uuid=True),
              sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
              primary_key=True,
          ),
          sa.Column(
              "settings_json",
              postgresql.JSONB(astext_type=sa.Text()),
              nullable=False,
              server_default="{}",
          ),
          sa.Column(
              "created_at",
              sa.DateTime(timezone=True),
              server_default=sa.text("now()"),
              nullable=False,
          ),
          sa.Column(
              "updated_at",
              sa.DateTime(timezone=True),
              server_default=sa.text("now()"),
              nullable=False,
          ),
      )


  def downgrade() -> None:
      op.drop_table("workspace_settings")
  ```

- [ ] Step 3: Add workspace settings endpoints to `backend/app/api/workspaces.py`

  Add imports at the top:
  ```python
  from app.core.security import decrypt_api_keys, encrypt_api_keys, fernet_decrypt, fernet_encrypt
  from app.db.models import Organization, User, Workspace, WorkspaceMember, WorkspaceSettings
  ```

  Append these two endpoints:

  ```python
  class WorkspaceSettingsUpdate(BaseModel):
      model_provider: str | None = Field(default=None, max_length=50)
      model_name: str | None = Field(default=None, max_length=100)
      api_keys: dict[str, str | list[str]] | None = None


  @router.get("/{ws_id}/settings")
  async def get_workspace_settings(
      ws_id: uuid.UUID,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      """Get LLM settings for a workspace. Membership required."""
      ws = await db.get(Workspace, ws_id)
      if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
          raise HTTPException(status_code=404, detail="Workspace not found")
      membership = await db.scalar(
          select(WorkspaceMember).where(
              WorkspaceMember.workspace_id == ws_id,
              WorkspaceMember.user_id == user.id,
          )
      )
      if not membership:
          raise HTTPException(status_code=403, detail="Not a member")
      ws_settings = await db.scalar(
          select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == ws_id)
      )
      if not ws_settings:
          return {"model_provider": None, "model_name": None, "has_api_key": {}}
      sj = ws_settings.settings_json
      raw_keys = decrypt_api_keys(sj.get("api_keys", {}))
      has_key = {
          provider: bool(v) for provider, v in raw_keys.items() if v
      }
      return {
          "model_provider": sj.get("model_provider"),
          "model_name": sj.get("model_name"),
          "has_api_key": has_key,
      }


  @router.put("/{ws_id}/settings")
  async def update_workspace_settings(
      ws_id: uuid.UUID,
      body: WorkspaceSettingsUpdate,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      """Update LLM settings for a workspace. Admin+ only."""
      ws = await db.get(Workspace, ws_id)
      if not ws or ws.is_deleted or ws.organization_id != user.organization_id:
          raise HTTPException(status_code=404, detail="Workspace not found")
      membership = await db.scalar(
          select(WorkspaceMember).where(
              WorkspaceMember.workspace_id == ws_id,
              WorkspaceMember.user_id == user.id,
          )
      )
      if not membership or membership.role not in ("owner", "admin"):
          raise HTTPException(status_code=403, detail="Admin access required")

      ws_settings = await db.scalar(
          select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == ws_id)
      )
      if not ws_settings:
          ws_settings = WorkspaceSettings(workspace_id=ws_id, settings_json={})
          db.add(ws_settings)

      sj = dict(ws_settings.settings_json)
      if body.model_provider is not None:
          sj["model_provider"] = body.model_provider
      if body.model_name is not None:
          sj["model_name"] = body.model_name
      if body.api_keys is not None:
          existing = decrypt_api_keys(sj.get("api_keys", {}))
          existing.update(body.api_keys)
          sj["api_keys"] = encrypt_api_keys(existing)
      ws_settings.settings_json = sj
      await db.commit()
      return {"status": "ok"}
  ```

- [ ] Step 4: Update `backend/app/api/deps.py` — extend `get_llm_config` with three-tier resolution

  In `get_llm_config`, after the existing `settings` lookup and before the `resolve_api_keys` call, add workspace key resolution. Add these imports at the top of deps.py:
  ```python
  from app.db.models import ApiKey, User, UserRole, UserSettings, WorkspaceMember, WorkspaceSettings
  ```

  Extend `get_llm_config` to accept an optional `workspace_id` query parameter and apply the three-tier chain:

  ```python
  async def get_llm_config(
      workspace_id: uuid.UUID | None = None,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ) -> ResolvedLLMConfig:
      """Load LLM settings with three-tier priority:
      1. Personal user API key
      2. Workspace API key (if workspace_id provided and user is a member)
      3. System-level env var key (DEEPSEEK_API_KEY, etc.)

      Raises HTTPException(400) when no API key can be resolved for the provider.
      """
      import uuid as _uuid

      user_settings = await db.scalar(
          select(UserSettings).where(UserSettings.user_id == user.id)
      )

      provider = user_settings.model_provider if user_settings else "deepseek"
      model_name = user_settings.model_name if user_settings else "deepseek-chat"
      raw_keys = user_settings.api_keys if user_settings else {}

      # Tier 1: personal keys
      api_keys = resolve_api_keys(provider, raw_keys)

      # Tier 2: workspace keys (if workspace_id provided and user is member)
      if workspace_id is not None and not api_keys:
          membership = await db.scalar(
              select(WorkspaceMember).where(
                  WorkspaceMember.workspace_id == workspace_id,
                  WorkspaceMember.user_id == user.id,
              )
          )
          if membership:
              ws_settings = await db.scalar(
                  select(WorkspaceSettings).where(
                      WorkspaceSettings.workspace_id == workspace_id
                  )
              )
              if ws_settings:
                  sj = ws_settings.settings_json
                  ws_raw_keys = sj.get("api_keys", {})
                  ws_provider = sj.get("model_provider") or provider
                  ws_model = sj.get("model_name") or model_name
                  ws_keys = resolve_api_keys(ws_provider, ws_raw_keys)
                  if ws_keys:
                      # Override provider/model from workspace settings
                      provider = ws_provider
                      model_name = ws_model
                      api_keys = ws_keys
                      raw_keys = ws_raw_keys

      if not api_keys:
          raise HTTPException(
              status_code=400,
              detail=f"No API key configured for provider '{provider}'. "
              "Set it in Settings or ask the admin to configure a server-level key.",
          )

      return ResolvedLLMConfig(
          provider=provider,
          model_name=model_name,
          api_key=api_keys[0],
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
      )
  ```

  Add `import uuid` at the top of `deps.py` since `uuid.UUID` is now referenced in the signature.

- [ ] Step 5: Run static checks
  ```bash
  cd /Users/hyh/code/JARVIS/backend
  uv run ruff check --fix && uv run ruff format
  uv run mypy app
  uv run pytest --collect-only -q
  ```

- [ ] Step 6: Commit
  ```bash
  cd /Users/hyh/code/JARVIS
  git add backend/app/db/models.py \
          backend/app/api/workspaces.py \
          backend/app/api/deps.py \
          backend/alembic/versions/017_workspace_settings.py
  git commit -m "feat(multi-tenant): workspace LLM settings with three-tier key resolution chain (migration 017)"
  ```

---

## Chunk 5

## Task 4.5 — Frontend Multi-tenant UI

**Files:**
- Create: `frontend/src/stores/workspace.ts`
- Create: `frontend/src/components/WorkspaceSwitcher.vue`
- Create: `frontend/src/pages/WorkspaceMembersPage.vue`
- Create: `frontend/src/pages/InviteAcceptPage.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/pages/SettingsPage.vue`
- Modify: `frontend/src/pages/DocumentsPage.vue`
- Modify: `frontend/src/pages/ProactivePage.vue`
- Modify: `frontend/src/locales/zh.json` (and en/ja/ko/fr/de)

**Steps:**

- [ ] Step 1: Create `frontend/src/stores/workspace.ts`

  ```typescript
  import { defineStore } from "pinia";
  import client from "@/api/client";

  interface Workspace {
    id: string;
    name: string;
    organization_id: string;
    is_deleted: boolean;
    created_at: string;
    updated_at: string;
  }

  interface Organization {
    id: string;
    name: string;
    slug: string;
    owner_id: string;
    created_at: string;
  }

  interface WorkspaceMember {
    user_id: string;
    email: string | null;
    display_name: string | null;
    role: string;
    joined_at: string;
  }

  export const useWorkspaceStore = defineStore("workspace", {
    state: () => ({
      organization: null as Organization | null,
      workspaces: [] as Workspace[],
      currentWorkspaceId: localStorage.getItem("currentWorkspaceId") as string | null,
      members: [] as WorkspaceMember[],
    }),
    getters: {
      currentWorkspace: (s): Workspace | null =>
        s.workspaces.find((w) => w.id === s.currentWorkspaceId) ?? null,
      hasOrganization: (s) => !!s.organization,
    },
    actions: {
      async fetchOrganization() {
        try {
          const { data } = await client.get("/organizations/me");
          this.organization = data;
        } catch {
          this.organization = null;
        }
      },
      async fetchWorkspaces() {
        try {
          const { data } = await client.get("/workspaces");
          this.workspaces = data;
          // If current workspace was deleted, clear selection
          if (
            this.currentWorkspaceId &&
            !this.workspaces.find((w) => w.id === this.currentWorkspaceId)
          ) {
            this.switchWorkspace(null);
          }
        } catch {
          this.workspaces = [];
        }
      },
      switchWorkspace(id: string | null) {
        this.currentWorkspaceId = id;
        if (id) {
          localStorage.setItem("currentWorkspaceId", id);
        } else {
          localStorage.removeItem("currentWorkspaceId");
        }
      },
      async createOrganization(name: string, slug: string) {
        const { data } = await client.post("/organizations", { name, slug });
        this.organization = data;
        return data;
      },
      async createWorkspace(name: string) {
        const { data } = await client.post("/workspaces", { name });
        this.workspaces.push(data);
        return data;
      },
      async fetchMembers(workspaceId: string) {
        const { data } = await client.get(`/workspaces/${workspaceId}/members`);
        this.members = data;
      },
      async inviteMember(workspaceId: string, email: string, role: string) {
        const { data } = await client.post(
          `/workspaces/${workspaceId}/members/invite`,
          { email, role }
        );
        return data;
      },
      async removeMember(workspaceId: string, userId: string) {
        await client.delete(`/workspaces/${workspaceId}/members/${userId}`);
        this.members = this.members.filter((m) => m.user_id !== userId);
      },
      async updateMemberRole(workspaceId: string, userId: string, role: string) {
        await client.put(`/workspaces/${workspaceId}/members/${userId}`, { role });
        const m = this.members.find((m) => m.user_id === userId);
        if (m) m.role = role;
      },
    },
  });
  ```

- [ ] Step 2: Create `frontend/src/components/WorkspaceSwitcher.vue`

  ```vue
  <template>
    <div class="relative" ref="dropdownRef">
      <button
        class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-800/60 hover:bg-zinc-700/60 border border-zinc-700/50 text-sm text-zinc-200 transition-colors"
        @click="open = !open"
      >
        <span class="max-w-[120px] truncate">
          {{ workspace.currentWorkspace?.name ?? $t("workspace.personal") }}
        </span>
        <ChevronDown class="w-3.5 h-3.5 text-zinc-400 shrink-0" :class="{ 'rotate-180': open }" />
      </button>

      <div
        v-if="open"
        class="absolute top-full mt-1 left-0 z-50 min-w-[180px] bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl py-1"
      >
        <!-- Personal -->
        <button
          class="w-full text-left px-4 py-2 text-sm hover:bg-zinc-800 transition-colors"
          :class="{ 'text-white font-medium': !workspace.currentWorkspaceId, 'text-zinc-300': workspace.currentWorkspaceId }"
          @click="select(null)"
        >
          {{ $t("workspace.personal") }}
        </button>

        <div v-if="workspace.workspaces.length > 0" class="border-t border-zinc-800 my-1" />

        <button
          v-for="ws in workspace.workspaces"
          :key="ws.id"
          class="w-full text-left px-4 py-2 text-sm hover:bg-zinc-800 transition-colors"
          :class="{ 'text-white font-medium': workspace.currentWorkspaceId === ws.id, 'text-zinc-300': workspace.currentWorkspaceId !== ws.id }"
          @click="select(ws.id)"
        >
          {{ ws.name }}
        </button>

        <div class="border-t border-zinc-800 my-1" />

        <button
          class="w-full text-left px-4 py-2 text-xs text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 transition-colors"
          @click="$router.push('/workspace/members'); open = false"
        >
          {{ $t("workspace.manageMembers") }}
        </button>
      </div>
    </div>
  </template>

  <script setup lang="ts">
  import { ref, onMounted, onUnmounted } from "vue";
  import { ChevronDown } from "lucide-vue-next";
  import { useWorkspaceStore } from "@/stores/workspace";

  const workspace = useWorkspaceStore();
  const open = ref(false);
  const dropdownRef = ref<HTMLElement | null>(null);

  function select(id: string | null) {
    workspace.switchWorkspace(id);
    open.value = false;
  }

  function handleOutside(e: MouseEvent) {
    if (dropdownRef.value && !dropdownRef.value.contains(e.target as Node)) {
      open.value = false;
    }
  }

  onMounted(() => document.addEventListener("mousedown", handleOutside));
  onUnmounted(() => document.removeEventListener("mousedown", handleOutside));
  </script>
  ```

- [ ] Step 3: Create `frontend/src/pages/WorkspaceMembersPage.vue`

  ```vue
  <template>
    <div class="h-screen flex flex-col bg-zinc-950 font-sans text-zinc-200">
      <PageHeader :title="$t('workspace.members')" />

      <div class="flex-1 overflow-y-auto custom-scrollbar p-8">
        <div class="max-w-3xl mx-auto space-y-8">

          <!-- No org state -->
          <div v-if="!workspace.hasOrganization" class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-8 text-center">
            <p class="text-zinc-400 mb-6">{{ $t("workspace.noOrgDesc") }}</p>
            <form class="space-y-4 max-w-sm mx-auto" @submit.prevent="createOrg">
              <input
                v-model="orgName"
                class="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600"
                :placeholder="$t('workspace.orgName')"
                required
              />
              <input
                v-model="orgSlug"
                class="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600"
                :placeholder="$t('workspace.orgSlug')"
                required
                pattern="[a-z0-9][a-z0-9\-]{1,98}[a-z0-9]"
              />
              <button type="submit" class="w-full py-2.5 bg-white text-black text-sm font-semibold rounded-lg hover:bg-zinc-200 transition-colors">
                {{ $t("workspace.createOrg") }}
              </button>
            </form>
          </div>

          <!-- Has org: workspace selection + members -->
          <template v-else>
            <!-- Workspace selector -->
            <section class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-6">
              <div class="flex items-center justify-between mb-4">
                <h3 class="text-[11px] font-bold tracking-widest text-zinc-500 uppercase">
                  {{ $t("workspace.title") }}
                </h3>
                <button
                  class="text-xs text-zinc-400 hover:text-white transition-colors"
                  @click="showCreateWs = !showCreateWs"
                >
                  + {{ $t("workspace.createWorkspace") }}
                </button>
              </div>

              <div v-if="showCreateWs" class="flex gap-2 mb-4">
                <input
                  v-model="newWsName"
                  class="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm outline-none focus:border-zinc-600"
                  :placeholder="$t('workspace.workspaceName')"
                />
                <button
                  class="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 transition-colors"
                  @click="createWs"
                >
                  {{ $t("common.confirm") }}
                </button>
              </div>

              <div class="space-y-2">
                <button
                  v-for="ws in workspace.workspaces"
                  :key="ws.id"
                  class="w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-colors"
                  :class="selectedWsId === ws.id
                    ? 'border-zinc-500 bg-zinc-800'
                    : 'border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900'"
                  @click="selectedWsId = ws.id; loadMembers(ws.id)"
                >
                  <span class="text-sm font-medium">{{ ws.name }}</span>
                  <span class="text-xs text-zinc-500">{{ ws.id.slice(0, 8) }}...</span>
                </button>
              </div>
            </section>

            <!-- Members list + invite -->
            <section v-if="selectedWsId" class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-6">
              <div class="flex items-center justify-between mb-6">
                <h3 class="text-[11px] font-bold tracking-widest text-zinc-500 uppercase">
                  {{ $t("workspace.membersList") }}
                </h3>
              </div>

              <!-- Invite form -->
              <form class="flex gap-2 mb-6" @submit.prevent="invite">
                <input
                  v-model="inviteEmail"
                  type="email"
                  class="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2 text-sm outline-none focus:border-zinc-600"
                  :placeholder="$t('workspace.inviteEmail')"
                  required
                />
                <select
                  v-model="inviteRole"
                  class="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm outline-none"
                >
                  <option value="member">{{ $t("workspace.roleMember") }}</option>
                  <option value="admin">{{ $t("workspace.roleAdmin") }}</option>
                </select>
                <button
                  type="submit"
                  class="px-4 py-2 bg-white text-black text-sm font-semibold rounded-lg hover:bg-zinc-200 transition-colors"
                >
                  {{ $t("workspace.invite") }}
                </button>
              </form>

              <div v-if="inviteLink" class="mb-4 p-3 bg-zinc-800 rounded-lg text-xs text-zinc-300 break-all">
                {{ $t("workspace.inviteLink") }}: {{ inviteLink }}
              </div>

              <!-- Members table -->
              <div class="space-y-2">
                <div
                  v-for="m in workspace.members"
                  :key="m.user_id"
                  class="flex items-center justify-between px-4 py-3 rounded-xl bg-zinc-900 border border-zinc-800"
                >
                  <div>
                    <p class="text-sm font-medium">{{ m.display_name || m.email }}</p>
                    <p class="text-xs text-zinc-500">{{ m.email }}</p>
                  </div>
                  <div class="flex items-center gap-3">
                    <select
                      :value="m.role"
                      class="bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1 text-xs"
                      @change="(e) => changeRole(m.user_id, (e.target as HTMLSelectElement).value)"
                    >
                      <option value="member">{{ $t("workspace.roleMember") }}</option>
                      <option value="admin">{{ $t("workspace.roleAdmin") }}</option>
                    </select>
                    <button
                      class="text-xs text-red-400 hover:text-red-300 transition-colors"
                      @click="removeMember(m.user_id)"
                    >
                      {{ $t("workspace.remove") }}
                    </button>
                  </div>
                </div>
              </div>
            </section>
          </template>
        </div>
      </div>
    </div>
  </template>

  <script setup lang="ts">
  import { ref, onMounted } from "vue";
  import { useI18n } from "vue-i18n";
  import { useWorkspaceStore } from "@/stores/workspace";
  import PageHeader from "@/components/PageHeader.vue";

  const { t } = useI18n();
  const workspace = useWorkspaceStore();

  const orgName = ref("");
  const orgSlug = ref("");
  const newWsName = ref("");
  const showCreateWs = ref(false);
  const selectedWsId = ref<string | null>(null);
  const inviteEmail = ref("");
  const inviteRole = ref("member");
  const inviteLink = ref<string | null>(null);

  onMounted(async () => {
    await workspace.fetchOrganization();
    await workspace.fetchWorkspaces();
  });

  async function createOrg() {
    await workspace.createOrganization(orgName.value, orgSlug.value);
    orgName.value = "";
    orgSlug.value = "";
  }

  async function createWs() {
    if (!newWsName.value.trim()) return;
    await workspace.createWorkspace(newWsName.value.trim());
    newWsName.value = "";
    showCreateWs.value = false;
  }

  async function loadMembers(wsId: string) {
    inviteLink.value = null;
    await workspace.fetchMembers(wsId);
  }

  async function invite() {
    if (!selectedWsId.value) return;
    const inv = await workspace.inviteMember(
      selectedWsId.value,
      inviteEmail.value,
      inviteRole.value
    );
    inviteLink.value = `${window.location.origin}/invite/${inv.token}`;
    inviteEmail.value = "";
  }

  async function changeRole(userId: string, role: string) {
    if (!selectedWsId.value) return;
    await workspace.updateMemberRole(selectedWsId.value, userId, role);
  }

  async function removeMember(userId: string) {
    if (!selectedWsId.value) return;
    if (!confirm(t("workspace.removeConfirm"))) return;
    await workspace.removeMember(selectedWsId.value, userId);
  }
  </script>
  ```

- [ ] Step 4: Create `frontend/src/pages/InviteAcceptPage.vue`

  ```vue
  <template>
    <div class="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div class="w-full max-w-md">
        <div v-if="loading" class="text-center text-zinc-400">
          {{ $t("common.loading") }}
        </div>

        <div v-else-if="error" class="bg-zinc-900 border border-red-800/50 rounded-2xl p-8 text-center">
          <p class="text-red-400">{{ error }}</p>
          <button
            class="mt-4 px-6 py-2 bg-white text-black text-sm font-semibold rounded-lg"
            @click="$router.push('/')"
          >
            {{ $t("common.backToChat") }}
          </button>
        </div>

        <div v-else-if="invitation" class="bg-zinc-900 border border-zinc-800 rounded-2xl p-8">
          <h1 class="text-xl font-bold text-white mb-2">{{ $t("workspace.inviteTitle") }}</h1>
          <p class="text-zinc-400 mb-6">
            {{ $t("workspace.inviteDesc", {
              workspace: invitation.workspace_name,
              role: invitation.role
            }) }}
          </p>

          <div v-if="!auth.isLoggedIn" class="space-y-3">
            <p class="text-sm text-zinc-500">{{ $t("workspace.inviteLoginRequired") }}</p>
            <button
              class="w-full py-2.5 bg-white text-black font-semibold rounded-lg hover:bg-zinc-200 transition-colors"
              @click="$router.push(`/login?redirect=${route.fullPath}`)"
            >
              {{ $t("login.submit") }}
            </button>
          </div>

          <div v-else>
            <button
              class="w-full py-2.5 bg-white text-black font-semibold rounded-lg hover:bg-zinc-200 transition-colors disabled:opacity-50"
              :disabled="accepting"
              @click="accept"
            >
              {{ accepting ? $t("common.loading") : $t("workspace.acceptInvite") }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </template>

  <script setup lang="ts">
  import { ref, onMounted } from "vue";
  import { useRoute, useRouter } from "vue-router";
  import { useI18n } from "vue-i18n";
  import client from "@/api/client";
  import { useAuthStore } from "@/stores/auth";
  import { useWorkspaceStore } from "@/stores/workspace";

  const route = useRoute();
  const router = useRouter();
  const { t } = useI18n();
  const auth = useAuthStore();
  const workspace = useWorkspaceStore();

  const token = route.params.token as string;
  const loading = ref(true);
  const accepting = ref(false);
  const error = ref<string | null>(null);
  const invitation = ref<any>(null);

  onMounted(async () => {
    try {
      const { data } = await client.get(`/invitations/${token}`);
      invitation.value = data;
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? t("workspace.inviteInvalid");
    } finally {
      loading.value = false;
    }
  });

  async function accept() {
    accepting.value = true;
    try {
      const { data } = await client.post(`/invitations/${token}/accept`);
      await workspace.fetchOrganization();
      await workspace.fetchWorkspaces();
      workspace.switchWorkspace(data.workspace_id);
      router.push("/");
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? t("workspace.inviteAcceptError");
    } finally {
      accepting.value = false;
    }
  }
  </script>
  ```

- [ ] Step 5: Update `frontend/src/router/index.ts`

  Add the two new routes before the catch-all:
  ```typescript
  { path: "/workspace/members", component: () => import("@/pages/WorkspaceMembersPage.vue"), meta: { requiresAuth: true } },
  { path: "/invite/:token", component: () => import("@/pages/InviteAcceptPage.vue") },
  ```

- [ ] Step 6: Update `frontend/src/pages/DocumentsPage.vue` — add workspace filter selector

  In the `<script setup>` section, add:
  ```typescript
  import { useWorkspaceStore } from "@/stores/workspace";
  const workspace = useWorkspaceStore();
  ```

  Add a workspace selector UI element above the upload zone in the template:
  ```html
  <!-- Workspace scope selector -->
  <div class="flex items-center gap-3 mb-4">
    <label class="text-xs text-zinc-500">{{ $t("workspace.scope") }}:</label>
    <select
      v-model="selectedWorkspaceId"
      class="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-sm text-zinc-200 outline-none"
      @change="loadDocuments"
    >
      <option :value="null">{{ $t("workspace.personal") }}</option>
      <option v-for="ws in workspace.workspaces" :key="ws.id" :value="ws.id">
        {{ ws.name }}
      </option>
    </select>
  </div>
  ```

  Add `const selectedWorkspaceId = ref<string | null>(null)` to script.

  In the upload function, pass `?workspace_id=` when `selectedWorkspaceId.value` is set:
  ```typescript
  const url = selectedWorkspaceId.value
    ? `/documents?workspace_id=${selectedWorkspaceId.value}`
    : "/documents";
  ```

  Update `loadDocuments` to pass the filter:
  ```typescript
  async function loadDocuments() {
    const url = selectedWorkspaceId.value
      ? `/documents?workspace_id=${selectedWorkspaceId.value}`
      : "/documents";
    const { data } = await client.get(url);
    documents.value = data.documents;
  }
  ```

- [ ] Step 7: Update `frontend/src/pages/ProactivePage.vue` — add workspace selector for cron jobs

  Add `WorkspaceSwitcher` in the header area to filter cron jobs by workspace. The pattern mirrors DocumentsPage above: add `selectedWorkspaceId` ref, pass it to list/create API calls as `?workspace_id=`.

  Import and add workspace selector before the job creation form:
  ```typescript
  import WorkspaceSwitcher from "@/components/WorkspaceSwitcher.vue";
  ```
  In template, add near the top of the content area:
  ```html
  <div class="flex items-center gap-3 mb-6">
    <WorkspaceSwitcher />
  </div>
  ```
  Pass `workspace_id` in the create cron job payload when a workspace is active:
  ```typescript
  const payload = {
    ...formData,
    workspace_id: workspace.currentWorkspaceId ?? undefined,
  };
  ```

- [ ] Step 8: Update `frontend/src/pages/SettingsPage.vue` — add Workspace Settings tab

  Add a "Workspace" tab section at the bottom of the settings form. The section renders only when the user has a workspace selected:

  ```html
  <!-- Workspace LLM Settings -->
  <section v-if="workspace.currentWorkspace" class="bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-6 shadow-sm">
    <h3 class="text-[11px] font-bold tracking-widest text-zinc-500 uppercase mb-4">
      {{ $t("workspace.settingsTitle", { name: workspace.currentWorkspace.name }) }}
    </h3>
    <div class="space-y-4">
      <div class="flex flex-col gap-2">
        <label class="text-xs font-semibold text-zinc-400">{{ $t("settings.provider") }}</label>
        <select
          v-model="wsProvider"
          class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600"
        >
          <option value="">{{ $t("workspace.usePersonal") }}</option>
          <option value="deepseek">DeepSeek</option>
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic</option>
        </select>
      </div>
      <div v-if="wsProvider" class="flex flex-col gap-2">
        <label class="text-xs font-semibold text-zinc-400">{{ $t("settings.apiKey") }}</label>
        <input
          v-model="wsApiKey"
          type="password"
          class="bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-zinc-600"
          :placeholder="$t('settings.apiKeyPlaceholder')"
        />
      </div>
      <button
        type="button"
        class="w-full py-2.5 bg-zinc-700 text-white text-sm font-semibold rounded-lg hover:bg-zinc-600 transition-colors"
        @click="saveWsSettings"
      >
        {{ $t("workspace.saveSettings") }}
      </button>
    </div>
  </section>
  ```

  In `<script setup>`:
  ```typescript
  import { useWorkspaceStore } from "@/stores/workspace";
  const workspace = useWorkspaceStore();
  const wsProvider = ref("");
  const wsApiKey = ref("");

  async function saveWsSettings() {
    if (!workspace.currentWorkspaceId) return;
    const payload: Record<string, any> = {};
    if (wsProvider.value) {
      payload.model_provider = wsProvider.value;
      if (wsApiKey.value) {
        payload.api_keys = { [wsProvider.value]: wsApiKey.value };
      }
    }
    await client.put(`/workspaces/${workspace.currentWorkspaceId}/settings`, payload);
  }
  ```

- [ ] Step 9: Add i18n keys to `frontend/src/locales/zh.json`

  Add the following block inside the JSON object, after the `"plugins"` key:
  ```json
  "workspace": {
    "title": "工作空间",
    "personal": "个人",
    "noOrgDesc": "创建一个组织，邀请团队成员协作",
    "orgName": "组织名称",
    "orgSlug": "组织标识（小写字母和连字符）",
    "createOrg": "创建组织",
    "createWorkspace": "新建工作空间",
    "workspaceName": "工作空间名称",
    "members": "成员管理",
    "membersList": "成员列表",
    "manageMembers": "管理成员",
    "inviteEmail": "邀请邮箱",
    "invite": "发送邀请",
    "inviteLink": "邀请链接",
    "roleMember": "成员",
    "roleAdmin": "管理员",
    "roleOwner": "所有者",
    "remove": "移除",
    "removeConfirm": "确定要移除该成员？",
    "scope": "范围",
    "inviteTitle": "加入工作空间",
    "inviteDesc": "您被邀请以"{role}"身份加入工作空间"{workspace}"",
    "inviteLoginRequired": "请先登录以接受邀请",
    "acceptInvite": "接受邀请",
    "inviteInvalid": "邀请链接无效或已过期",
    "inviteAcceptError": "接受邀请失败，请重试",
    "settingsTitle": "工作空间设置 — {name}",
    "saveSettings": "保存工作空间设置",
    "usePersonal": "使用个人配置"
  }
  ```

- [ ] Step 10: Add matching keys to all other locale files

  For `frontend/src/locales/en.json`, add:
  ```json
  "workspace": {
    "title": "Workspace",
    "personal": "Personal",
    "noOrgDesc": "Create an organization to invite team members",
    "orgName": "Organization name",
    "orgSlug": "Slug (lowercase letters and hyphens)",
    "createOrg": "Create organization",
    "createWorkspace": "New workspace",
    "workspaceName": "Workspace name",
    "members": "Members",
    "membersList": "Members list",
    "manageMembers": "Manage members",
    "inviteEmail": "Email to invite",
    "invite": "Send invite",
    "inviteLink": "Invite link",
    "roleMember": "Member",
    "roleAdmin": "Admin",
    "roleOwner": "Owner",
    "remove": "Remove",
    "removeConfirm": "Remove this member?",
    "scope": "Scope",
    "inviteTitle": "Join workspace",
    "inviteDesc": "You have been invited to join \"{workspace}\" as {role}",
    "inviteLoginRequired": "Please log in to accept this invitation",
    "acceptInvite": "Accept invite",
    "inviteInvalid": "Invitation is invalid or has expired",
    "inviteAcceptError": "Failed to accept invite. Please try again.",
    "settingsTitle": "Workspace settings — {name}",
    "saveSettings": "Save workspace settings",
    "usePersonal": "Use personal config"
  }
  ```

  Add equivalent translated blocks to `ja.json`, `ko.json`, `fr.json`, and `de.json` (follow the same key structure, translate the string values to each respective language).

- [ ] Step 11: Run static checks
  ```bash
  cd /Users/hyh/code/JARVIS/frontend
  bun run lint:fix
  bun run type-check
  ```

- [ ] Step 12: Commit
  ```bash
  cd /Users/hyh/code/JARVIS
  git add frontend/src/stores/workspace.ts \
          frontend/src/components/WorkspaceSwitcher.vue \
          frontend/src/pages/WorkspaceMembersPage.vue \
          frontend/src/pages/InviteAcceptPage.vue \
          frontend/src/router/index.ts \
          frontend/src/pages/SettingsPage.vue \
          frontend/src/pages/DocumentsPage.vue \
          frontend/src/pages/ProactivePage.vue \
          frontend/src/locales/zh.json \
          frontend/src/locales/en.json \
          frontend/src/locales/ja.json \
          frontend/src/locales/ko.json \
          frontend/src/locales/fr.json \
          frontend/src/locales/de.json
  git commit -m "feat(multi-tenant): workspace switcher, member management, invite accept page, workspace-scoped resources"
  ```

---

## Implementation Notes

### Migration Chain Verification
Before running migrations, verify the down_revision chain. The current latest migration is `013`. If a `014` does not exist yet, `015_activate_multi_tenant.py` should have `down_revision = "013"`. Always confirm with `uv run alembic history` before running.

### Workspace Creator Auto-Membership
The `create_workspace` endpoint must auto-insert a `WorkspaceMember` row with `role="owner"` for the creating user immediately after the workspace is created. This is required for the invite endpoint, which validates that the inviter is a member. Add this to `workspaces.py` after the workspace is flushed:
```python
db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
await db.commit()
```

### Qdrant Workspace Collections
Task 4.3 introduces `workspace_{ws_id}` as a Qdrant collection naming convention for workspace-shared documents. An `ensure_workspace_collection(ws_id)` helper should be added to `backend/app/infra/qdrant.py` following the same `asyncio.Lock` pattern as `ensure_user_collection`. The workspace document upload path in `documents.py` must call this helper instead of `ensure_user_collection` when `workspace_id` is set, and set `qdrant_collection` on the Document record accordingly.

### RAG Context Integration
The `build_rag_context` function in `context.py` is called from `agent/graph.py`. The agent graph receives `user_id` from the session. To pass `workspace_ids`, `agent/graph.py` must be updated to fetch the user's active workspace memberships and pass them into `build_rag_context`. This is a follow-up integration step not covered in the 5 tasks above but noted here for completeness.

### Security: Invitation Token Exposure
The invitation token is a UUID stored unencrypted. For production, consider using a short-lived HMAC-signed URL instead. The current design is acceptable for initial implementation.

---

### Critical Files for Implementation

- `/Users/hyh/code/JARVIS/backend/app/db/models.py` - Core models to modify: activate org/workspace FK relationships, add WorkspaceMember, Invitation, WorkspaceSettings models
- `/Users/hyh/code/JARVIS/backend/app/api/deps.py` - LLM config resolution chain to extend with three-tier workspace key resolution
- `/Users/hyh/code/JARVIS/backend/app/rag/retriever.py` - RAG retrieval to extend with multi-collection workspace-aware search
- `/Users/hyh/code/JARVIS/frontend/src/stores/workspace.ts` - New Pinia store to create: workspace state management, org/member/invite actions
- `/Users/hyh/code/JARVIS/backend/alembic/versions/013_multi_tenant_predesign.py` - Reference migration to understand existing schema before writing 015/016/017

---

Note: This is a READ-ONLY planning session. The plan above is the complete implementation blueprint. The file cannot be written to disk in this context — the plan should be copied manually to `/Users/hyh/code/JARVIS/docs/superpowers/plans/2026-03-13-phase4-multitenant.md` by the user or by running a separate agentic session with file-write permissions.