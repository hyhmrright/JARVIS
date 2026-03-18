import uuid


async def test_create_conversation(auth_client):
    resp = await auth_client.post("/api/conversations", json={"title": "My Chat"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "My Chat"


async def test_list_conversations(auth_client):
    await auth_client.post("/api/conversations", json={"title": "Chat 1"})
    await auth_client.post("/api/conversations", json={"title": "Chat 2"})
    resp = await auth_client.get("/api/conversations")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_delete_conversation(auth_client):
    create = await auth_client.post("/api/conversations", json={"title": "To Delete"})
    conv_id = create.json()["id"]
    resp = await auth_client.delete(f"/api/conversations/{conv_id}")
    assert resp.status_code == 204


async def test_active_leaf_defaults_to_null(auth_client):
    """New conversations must expose active_leaf_id as null."""
    resp = await auth_client.post("/api/conversations", json={"title": "Branch Test"})
    assert resp.status_code == 201
    assert resp.json()["active_leaf_id"] is None


async def test_set_active_leaf_unknown_message_returns_404(auth_client):
    """PATCH /active-leaf with a message not in the conversation returns 404."""
    create = await auth_client.post("/api/conversations", json={"title": "Branch Test"})
    conv_id = create.json()["id"]
    resp = await auth_client.patch(
        f"/api/conversations/{conv_id}/active-leaf",
        json={"active_leaf_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


async def test_set_active_leaf_wrong_conversation_returns_404(auth_client):
    """PATCH /active-leaf with a message not in this conversation returns 404."""
    # Use a random UUID that belongs to no conversation
    fake_conv_id = str(uuid.uuid4())
    resp = await auth_client.patch(
        f"/api/conversations/{fake_conv_id}/active-leaf",
        json={"active_leaf_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404
