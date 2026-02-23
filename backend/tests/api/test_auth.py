import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


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
    payload = {"email": "dup@example.com", "password": "pass123"}
    await client.post("/api/auth/register", json=payload)
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409


async def test_login_success(client):
    await client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "password": "pass123"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "pass123"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_wrong_password(client):
    await client.post(
        "/api/auth/register",
        json={"email": "wp@example.com", "password": "correct"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "wp@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401
