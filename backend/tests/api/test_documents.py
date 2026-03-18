import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.anyio
async def test_ingest_url_blocks_private_ip(auth_client):
    resp = await auth_client.post(
        "/api/documents/ingest-url",
        json={"url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert resp.status_code == 400
    assert "not allowed" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_ingest_url_blocks_localhost(auth_client):
    resp = await auth_client.post(
        "/api/documents/ingest-url",
        json={"url": "http://localhost:8080/secret"},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_ingest_url_rejects_non_http(auth_client):
    resp = await auth_client.post(
        "/api/documents/ingest-url",
        json={"url": "file:///etc/passwd"},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_ingest_url_success(auth_client, db_session):
    html_content = (
        b"<html><head><title>ML Guide</title></head>"
        b"<body><p>Machine learning is fascinating.</p></body></html>"
    )
    mock_resp = MagicMock()
    mock_resp.content = html_content
    mock_resp.raise_for_status = MagicMock()

    with (
        patch("app.api.documents.httpx") as mock_httpx,
        patch(
            "app.api.documents.asyncio.to_thread",
            side_effect=[
                ("ML Guide", "Machine learning is fascinating."),
                None,
            ],
        ),
        patch("app.api.documents.index_document", new=AsyncMock(return_value=5)),
        patch("app.api.documents.resolve_api_key", return_value="sk-fake"),
    ):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_ctx.get = AsyncMock(return_value=mock_resp)
        mock_httpx.AsyncClient.return_value = mock_ctx

        resp = await auth_client.post(
            "/api/documents/ingest-url",
            json={"url": "https://example.com/ml-guide"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["file_type"] == "txt"
    assert data["source_url"] == "https://example.com/ml-guide"
    assert "filename" in data
