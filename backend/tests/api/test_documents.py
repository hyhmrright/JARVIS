from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
    mock_resp.headers = {"content-type": "text/html; charset=utf-8"}

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


def test_extract_page_text_basic_html():
    from app.api.documents import _extract_page_text

    html = (
        b"<html><head><title>Test Title</title></head>"
        b"<body>"
        b"<nav>skip this</nav>"
        b"<p>First paragraph.</p>"
        b"<h2>Section Header</h2>"
        b"<li>List item</li>"
        b"<script>skip script</script>"
        b"</body></html>"
    )
    title, text = _extract_page_text(html, "https://example.com/page")
    assert title == "Test Title"
    assert "First paragraph." in text
    assert "Section Header" in text
    assert "List item" in text
    assert "skip this" not in text
    assert "skip script" not in text


def test_extract_page_text_fallback_to_h1():
    from app.api.documents import _extract_page_text

    html = b"<html><body><h1>Page Heading</h1><p>Content here.</p></body></html>"
    title, text = _extract_page_text(html, "https://example.com")
    assert title == "Page Heading"


def test_extract_page_text_fallback_to_hostname():
    from app.api.documents import _extract_page_text

    html = b"<html><body><p>No title here.</p></body></html>"
    title, text = _extract_page_text(html, "https://docs.example.org/page")
    assert title == "docs.example.org"


def _make_mock_http_ctx(content: bytes, content_type: str = "text/html; charset=utf-8"):
    """Helper: build a mock httpx.AsyncClient context for ingest-url tests."""
    mock_resp = MagicMock()
    mock_resp.content = content
    mock_resp.raise_for_status = MagicMock()
    mock_resp.headers = {"content-type": content_type}
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_ctx.get = AsyncMock(return_value=mock_resp)
    return mock_ctx


@pytest.mark.anyio
async def test_ingest_url_rejects_non_html_content_type(auth_client):
    """PDF or JSON responses should be rejected with 400."""
    with (
        patch("app.api.documents.httpx") as mock_httpx,
        patch("app.api.documents.resolve_api_key", return_value="sk-fake"),
    ):
        mock_httpx.AsyncClient.return_value = _make_mock_http_ctx(
            b"%PDF-1.4 ...", "application/pdf"
        )
        resp = await auth_client.post(
            "/api/documents/ingest-url",
            json={"url": "https://example.com/doc.pdf"},
        )
    assert resp.status_code == 400
    assert "non-text" in resp.json()["detail"]


@pytest.mark.anyio
async def test_ingest_url_accepts_plain_text_content_type(auth_client, db_session):
    """text/plain responses should be accepted."""
    with (
        patch("app.api.documents.httpx") as mock_httpx,
        patch(
            "app.api.documents.asyncio.to_thread",
            side_effect=[("plain.txt", "Hello world plain text content."), None],
        ),
        patch("app.api.documents.index_document", new=AsyncMock(return_value=2)),
        patch("app.api.documents.resolve_api_key", return_value="sk-fake"),
    ):
        mock_httpx.AsyncClient.return_value = _make_mock_http_ctx(
            b"Hello world plain text content.", "text/plain; charset=utf-8"
        )
        resp = await auth_client.post(
            "/api/documents/ingest-url",
            json={"url": "https://example.com/readme.txt"},
        )
    assert resp.status_code == 201


@pytest.mark.anyio
async def test_ingest_url_rejects_empty_page(auth_client):
    """Pages with no readable content should return 400."""
    with (
        patch("app.api.documents.httpx") as mock_httpx,
        patch(
            "app.api.documents.asyncio.to_thread",
            side_effect=[("example.com", "")],
        ),
        patch("app.api.documents.resolve_api_key", return_value="sk-fake"),
    ):
        mock_httpx.AsyncClient.return_value = _make_mock_http_ctx(b"<html></html>")
        resp = await auth_client.post(
            "/api/documents/ingest-url",
            json={"url": "https://example.com/empty"},
        )
    assert resp.status_code == 400
    assert "No readable content" in resp.json()["detail"]
