async def test_register_success(client):
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "password123",
            "display_name": "Test User",
        },
    )
    assert resp.status_code == 201
    assert "access_token" in resp.json()


async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "pass1234"}
    await client.post("/api/auth/register", json=payload)
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409


async def test_login_success(client):
    await client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "password": "pass1234"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "pass1234"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_register_rejects_password_over_72_bytes(client):
    payload = {"email": "big@example.com", "password": "\U0001f600" * 19}  # 76 bytes
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 422


async def test_login_wrong_password(client):
    await client.post(
        "/api/auth/register",
        json={"email": "wp@example.com", "password": "correct1"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "wp@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


async def test_change_password_success(client, auth_client):
    resp = await auth_client.post(
        "/api/auth/change-password",
        json={"current_password": "password123", "new_password": "newpassword456"},
    )
    assert resp.status_code == 204


async def test_change_password_wrong_current(client, auth_client):
    resp = await auth_client.post(
        "/api/auth/change-password",
        json={"current_password": "wrongpassword", "new_password": "newpassword456"},
    )
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["detail"].lower()


async def test_change_password_too_short(client, auth_client):
    resp = await auth_client.post(
        "/api/auth/change-password",
        json={"current_password": "password123", "new_password": "short"},
    )
    assert resp.status_code == 422


async def test_change_password_requires_auth(client):
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "password123", "new_password": "newpassword456"},
    )
    assert resp.status_code == 401
