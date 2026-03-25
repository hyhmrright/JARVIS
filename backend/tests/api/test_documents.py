import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import Document


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


@pytest.mark.anyio
async def test_upload_rejects_disguised_executable(auth_client):
    """File with .txt extension but ELF magic bytes must be rejected."""
    # Minimal 64-bit LE ELF header — libmagic detects this as
    # application/octet-stream (or ELF), which is not in ALLOWED_MIME_PREFIXES.
    elf_magic = (
        b"\x7fELF"  # magic
        b"\x02"  # EI_CLASS: 64-bit
        b"\x01"  # EI_DATA: little-endian
        b"\x01"  # EI_VERSION
        b"\x00"  # EI_OSABI
        + b"\x00" * 8  # EI_ABIVERSION + padding
        + b"\x02\x00"  # e_type: ET_EXEC
        + b"\x3e\x00"  # e_machine: x86-64
        + b"\x01\x00\x00\x00"  # e_version
        + b"\x00" * 200  # rest of header
    )
    resp = await auth_client.post(
        "/api/documents",
        files={"file": ("evil.txt", elf_magic, "text/plain")},
    )
    assert resp.status_code == 400


async def _create_test_document(db_session, user_id: uuid.UUID) -> uuid.UUID:
    """Insert a minimal Document row directly into the test DB."""
    doc = Document(
        user_id=user_id,
        filename="original.txt",
        file_type="txt",
        file_size_bytes=100,
        qdrant_collection=f"user_{user_id}",
        minio_object_key=f"{user_id}/{uuid.uuid4()}_original.txt",
    )
    db_session.add(doc)
    await db_session.flush()
    return doc.id


async def _get_user_id(auth_client) -> uuid.UUID:
    """Get the authenticated user's ID via the /api/auth/me endpoint."""
    resp = await auth_client.get("/api/auth/me")
    return uuid.UUID(resp.json()["id"])


@pytest.mark.anyio
async def test_rename_document(auth_client, db_session):
    """Renaming a document updates its filename and returns the updated doc."""
    user_id = await _get_user_id(auth_client)
    doc_id = await _create_test_document(db_session, user_id)

    resp = await auth_client.patch(
        f"/api/documents/{doc_id}", json={"filename": "renamed.txt"}
    )
    assert resp.status_code == 200
    assert resp.json()["filename"] == "renamed.txt"
    assert resp.json()["id"] == str(doc_id)


@pytest.mark.anyio
async def test_rename_document_empty_name_rejected(auth_client, db_session):
    """Empty filename should be rejected with 422."""
    user_id = await _get_user_id(auth_client)
    doc_id = await _create_test_document(db_session, user_id)

    resp = await auth_client.patch(f"/api/documents/{doc_id}", json={"filename": ""})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_rename_nonexistent_document(auth_client):
    """Renaming a non-existent document returns 404."""
    resp = await auth_client.patch(
        f"/api/documents/{uuid.uuid4()}", json={"filename": "x.txt"}
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_cannot_rename_other_users_document(auth_client, db_session, client):
    """Renaming another user's document should return 404."""
    from tests.conftest import _register_test_user

    user_id = await _get_user_id(auth_client)
    doc_id = await _create_test_document(db_session, user_id)

    # Authenticate as a different user
    token2 = await _register_test_user(client)
    client.headers["Authorization"] = f"Bearer {token2}"
    resp = await client.patch(
        f"/api/documents/{doc_id}", json={"filename": "hacked.txt"}
    )
    assert resp.status_code == 404
