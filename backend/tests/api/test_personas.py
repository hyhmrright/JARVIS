import uuid

import pytest


@pytest.mark.anyio
async def test_list_personas_empty(auth_client):
    resp = await auth_client.get("/api/personas")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.anyio
async def test_create_persona(auth_client):
    resp = await auth_client.post(
        "/api/personas",
        json={
            "name": "Test Bot",
            "description": "A test persona",
            "system_prompt": "You are a test bot.",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Bot"
    assert data["description"] == "A test persona"
    assert data["system_prompt"] == "You are a test bot."
    assert "id" in data


@pytest.mark.anyio
async def test_update_persona(auth_client):
    create_resp = await auth_client.post(
        "/api/personas",
        json={"name": "Old Name", "description": None, "system_prompt": "Old prompt."},
    )
    assert create_resp.status_code == 201
    persona_id = create_resp.json()["id"]

    update_resp = await auth_client.put(
        f"/api/personas/{persona_id}",
        json={
            "name": "New Name",
            "description": "Updated",
            "system_prompt": "New prompt.",
        },
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["name"] == "New Name"
    assert data["description"] == "Updated"


@pytest.mark.anyio
async def test_delete_persona(auth_client):
    create_resp = await auth_client.post(
        "/api/personas",
        json={"name": "To Delete", "description": None, "system_prompt": "Delete me."},
    )
    assert create_resp.status_code == 201
    persona_id = create_resp.json()["id"]

    del_resp = await auth_client.delete(f"/api/personas/{persona_id}")
    assert del_resp.status_code == 200

    list_resp = await auth_client.get("/api/personas")
    ids = [p["id"] for p in list_resp.json()["items"]]
    assert persona_id not in ids


@pytest.mark.anyio
async def test_clone_persona(auth_client):
    create_resp = await auth_client.post(
        "/api/personas",
        json={
            "name": "Original",
            "description": "Desc",
            "system_prompt": "Be helpful.",
        },
    )
    assert create_resp.status_code == 201
    original_id = create_resp.json()["id"]

    clone_resp = await auth_client.post(f"/api/personas/{original_id}/clone")
    assert clone_resp.status_code == 201
    clone = clone_resp.json()
    assert clone["name"] == "Original (copy)"
    assert clone["description"] == "Desc"
    assert clone["system_prompt"] == "Be helpful."
    assert clone["id"] != original_id


@pytest.mark.anyio
async def test_clone_persona_no_double_copy_suffix(auth_client):
    """Cloning a clone should not stack '(copy)' suffixes."""
    create_resp = await auth_client.post(
        "/api/personas",
        json={
            "name": "Foo (copy)",
            "description": None,
            "system_prompt": "Be helpful.",
        },
    )
    assert create_resp.status_code == 201
    original_id = create_resp.json()["id"]

    clone_resp = await auth_client.post(f"/api/personas/{original_id}/clone")
    assert clone_resp.status_code == 201
    assert clone_resp.json()["name"] == "Foo (copy)"


@pytest.mark.anyio
async def test_clone_persona_ownership(auth_client, client):
    """Cloning another user's persona returns 404."""
    from tests.conftest import _register_test_user

    token2 = await _register_test_user(client)
    create_resp = await auth_client.post(
        "/api/personas",
        json={"name": "Private", "description": None, "system_prompt": "Secret."},
    )
    assert create_resp.status_code == 201
    persona_id = create_resp.json()["id"]

    client.headers["Authorization"] = f"Bearer {token2}"
    clone_resp = await client.post(f"/api/personas/{persona_id}/clone")
    assert clone_resp.status_code == 404


@pytest.mark.anyio
async def test_clone_persona_not_found(auth_client):
    resp = await auth_client.post(f"/api/personas/{uuid.uuid4()}/clone")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_create_persona_with_extended_fields(auth_client):
    """Persona creation accepts new fields: temperature, model_name, enabled_tools, replace_system_prompt."""  # noqa: E501
    resp = await auth_client.post(
        "/api/personas",
        json={
            "name": "Extended Persona",
            "system_prompt": "You are a helpful assistant.",
            "temperature": 0.7,
            "model_name": "deepseek-chat",
            "enabled_tools": ["web_search", "code_exec"],
            "replace_system_prompt": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["temperature"] == 0.7
    assert data["model_name"] == "deepseek-chat"
    assert data["enabled_tools"] == ["web_search", "code_exec"]
    assert data["replace_system_prompt"] is True


@pytest.mark.anyio
async def test_persona_defaults_for_new_fields(auth_client):
    """Creating persona without new fields gives sane defaults."""
    resp = await auth_client.post(
        "/api/personas",
        json={"name": "Simple Persona", "system_prompt": "Be helpful."},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["temperature"] is None
    assert data["model_name"] is None
    assert data["enabled_tools"] is None
    assert data["replace_system_prompt"] is False
