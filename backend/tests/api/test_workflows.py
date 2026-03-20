import uuid

import pytest


@pytest.mark.anyio
async def test_list_workflows_empty(auth_client):
    resp = await auth_client.get("/api/workflows")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_create_workflow(auth_client):
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
async def test_get_workflow(auth_client):
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
async def test_update_workflow(auth_client):
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
            "dsl": {"nodes": [{"id": "1"}]},
        },
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["name"] == "New"
    assert data["description"] == "Updated desc"


@pytest.mark.anyio
async def test_delete_workflow(auth_client):
    create_resp = await auth_client.post(
        "/api/workflows",
        json={"name": "Delete Me", "description": None, "dsl": {}},
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    del_resp = await auth_client.delete(f"/api/workflows/{workflow_id}")
    assert del_resp.status_code == 200

    list_resp = await auth_client.get("/api/workflows")
    ids = [w["id"] for w in list_resp.json()]
    assert workflow_id not in ids


@pytest.mark.anyio
async def test_clone_workflow(auth_client):
    create_resp = await auth_client.post(
        "/api/workflows",
        json={
            "name": "Original Flow",
            "description": "Desc",
            "dsl": {"nodes": [{"id": "n1", "data": {"nested": [1, 2]}}]},
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
