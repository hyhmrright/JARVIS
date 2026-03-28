import uuid

import pytest


@pytest.mark.anyio
async def test_list_workflows_empty(auth_client):
    resp = await auth_client.get("/api/workflows")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.anyio
async def test_create_workflow_returns_201_with_id(auth_client):
    resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "My Flow",
            "description": "Test workflow",
            "dsl": {"nodes": [], "edges": []},
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Flow"
    assert data["description"] == "Test workflow"
    assert data["dsl"] == {"nodes": [], "edges": []}
    assert "id" in data


@pytest.mark.anyio
async def test_get_workflow_returns_stored_name(auth_client):
    create_resp = await auth_client.post(
        "/api/workflows",
        json={"name": "Fetchable", "description": None, "dsl": {}},
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    get_resp = await auth_client.get(f"/api/workflows/{workflow_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Fetchable"


@pytest.mark.anyio
async def test_update_workflow_persists_new_name_and_description(auth_client):
    create_resp = await auth_client.post(
        "/api/workflows",
        json={"name": "Old", "description": None, "dsl": {}},
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    update_resp = await auth_client.put(
        f"/api/workflows/{workflow_id}",
        json={
            "name": "New",
            "description": "Updated desc",
            "dsl": {"nodes": [{"id": "n1", "type": "llm", "data": {}}]},
        },
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["name"] == "New"
    assert data["description"] == "Updated desc"


@pytest.mark.anyio
async def test_delete_workflow_removes_it_from_list(auth_client):
    create_resp = await auth_client.post(
        "/api/workflows",
        json={"name": "Delete Me", "description": None, "dsl": {}},
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    del_resp = await auth_client.delete(f"/api/workflows/{workflow_id}")
    assert del_resp.status_code == 200

    list_resp = await auth_client.get("/api/workflows")
    ids = [w["id"] for w in list_resp.json()["items"]]
    assert workflow_id not in ids


@pytest.mark.anyio
async def test_clone_workflow_creates_copy_with_suffix(auth_client):
    create_resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "Original Flow",
            "description": "Desc",
            "dsl": {"nodes": [{"id": "n1", "type": "llm", "data": {"nested": [1, 2]}}]},
        },
    )
    assert create_resp.status_code == 201
    original = create_resp.json()

    clone_resp = await auth_client.post(f"/api/workflows/{original['id']}/clone")
    assert clone_resp.status_code == 201
    clone = clone_resp.json()
    assert clone["name"] == "Original Flow (copy)"
    assert clone["description"] == "Desc"
    assert clone["dsl"] == original["dsl"]
    assert clone["id"] != original["id"]


@pytest.mark.anyio
async def test_clone_workflow_no_double_copy_suffix(auth_client):
    """Cloning a clone should not stack '(copy)' suffixes."""
    create_resp = await auth_client.post(
        "/api/workflows",
        json={"name": "My Flow (copy)", "description": None, "dsl": {}},
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    clone_resp = await auth_client.post(f"/api/workflows/{workflow_id}/clone")
    assert clone_resp.status_code == 201
    assert clone_resp.json()["name"] == "My Flow (copy)"


@pytest.mark.anyio
async def test_clone_workflow_ownership(auth_client, client):
    """Cloning another user's workflow returns 404."""
    from tests.conftest import _register_test_user

    token2 = await _register_test_user(client)
    create_resp = await auth_client.post(
        "/api/workflows",
        json={"name": "Private Flow", "description": None, "dsl": {}},
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    client.headers["Authorization"] = f"Bearer {token2}"
    clone_resp = await client.post(f"/api/workflows/{workflow_id}/clone")
    assert clone_resp.status_code == 404


@pytest.mark.anyio
async def test_clone_workflow_not_found(auth_client):
    resp = await auth_client.post(f"/api/workflows/{uuid.uuid4()}/clone")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DSL validation tests (Phase 18 Task 1)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_workflow_with_invalid_dsl_rejected(auth_client):
    """DSL with unknown node type must be rejected with 422."""
    resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "Invalid DSL",
            "dsl": {
                "nodes": [{"id": "n1", "type": "unknown_type", "data": {}}],
                "edges": [],
            },
        },
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_workflow_with_cycle_rejected(auth_client):
    """DSL with cycle must be rejected with 422."""
    resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "Cyclic DSL",
            "dsl": {
                "nodes": [
                    {"id": "n1", "type": "llm", "data": {"prompt": "a"}},
                    {"id": "n2", "type": "llm", "data": {"prompt": "b"}},
                ],
                "edges": [
                    {"id": "e1", "source": "n1", "target": "n2"},
                    {"id": "e2", "source": "n2", "target": "n1"},
                ],
            },
        },
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_create_workflow_with_valid_dsl(auth_client):
    """Valid DSL with recognized node types passes validation."""
    resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "Valid Workflow",
            "dsl": {
                "nodes": [
                    {"id": "input_1", "type": "input", "data": {}},
                    {
                        "id": "llm_1",
                        "type": "llm",
                        "data": {"prompt": "Hello", "model": "deepseek-chat"},
                    },
                    {"id": "output_1", "type": "output", "data": {"format": "text"}},
                ],
                "edges": [
                    {"id": "e1", "source": "input_1", "target": "llm_1"},
                    {"id": "e2", "source": "llm_1", "target": "output_1"},
                ],
            },
        },
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Valid Workflow"


@pytest.mark.anyio
async def test_list_workflows(auth_client):
    """GET /workflows returns user's workflows."""
    resp = await auth_client.get("/api/workflows")
    assert resp.status_code == 200
    assert isinstance(resp.json()["items"], list)


@pytest.mark.anyio
async def test_delete_workflow_dsl(auth_client):
    """DELETE /workflows/{id} removes the workflow."""
    create_resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "To Delete",
            "dsl": {
                "nodes": [{"id": "n1", "type": "input", "data": {}}],
                "edges": [],
            },
        },
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    del_resp = await auth_client.delete(f"/api/workflows/{wf_id}")
    assert del_resp.status_code == 200


# ---------------------------------------------------------------------------
# Workflow runs tests (Phase 18 Task 3)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_workflow_runs(auth_client):
    """GET /runs returns list of run records."""
    create_resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "Runs Test",
            "dsl": {
                "nodes": [{"id": "input_1", "type": "input", "data": {}}],
                "edges": [],
            },
        },
    )
    assert create_resp.status_code == 201
    wf_id = create_resp.json()["id"]

    resp = await auth_client.get(f"/api/workflows/{wf_id}/runs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)  # workflow runs not paginated


@pytest.mark.anyio
async def test_list_workflow_runs_not_found(auth_client):
    """GET /runs for nonexistent workflow returns 404."""
    resp = await auth_client.get(f"/api/workflows/{uuid.uuid4()}/runs")
    assert resp.status_code == 404
