"""Tests for the chat file extraction endpoint."""

from unittest.mock import patch

import pytest


@pytest.mark.anyio
async def test_upload_rejects_unsupported_mime(auth_client):
    """Non-allowed MIME types must be rejected with 415."""
    resp = await auth_client.post(
        "/api/chat/extract-file",
        files={"file": ("evil.exe", b"MZ\x00\x00", "application/octet-stream")},
    )
    assert resp.status_code == 415


@pytest.mark.anyio
async def test_upload_rejects_image_mime(auth_client):
    """Image files (e.g. PNG) must be rejected with 415."""
    resp = await auth_client.post(
        "/api/chat/extract-file",
        files={"file": ("photo.png", b"\x89PNG\r\n", "image/png")},
    )
    assert resp.status_code == 415


@pytest.mark.anyio
async def test_upload_accepts_plain_text(auth_client):
    """Plain text files should be accepted and the text returned."""
    content = b"Hello, this is a test document."
    resp = await auth_client.post(
        "/api/chat/extract-file",
        files={"file": ("note.txt", content, "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "note.txt"
    assert "Hello" in data["extracted_text"]
    assert data["char_count"] > 0


@pytest.mark.anyio
async def test_upload_accepts_csv(auth_client):
    """CSV files should be accepted and text returned."""
    content = b"name,age\nAlice,30\nBob,25\n"
    resp = await auth_client.post(
        "/api/chat/extract-file",
        files={"file": ("data.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    assert "Alice" in resp.json()["extracted_text"]


@pytest.mark.anyio
async def test_upload_accepts_pdf(auth_client):
    """PDF upload with a mocked extractor should return 200."""
    fake_pdf = b"%PDF-1.4 minimal"
    with patch("app.api.chat_files._extract", return_value="Extracted PDF text"):
        resp = await auth_client.post(
            "/api/chat/extract-file",
            files={"file": ("doc.pdf", fake_pdf, "application/pdf")},
        )
    assert resp.status_code == 200
    assert resp.json()["extracted_text"] == "Extracted PDF text"


@pytest.mark.anyio
async def test_upload_rejects_oversized_file(auth_client):
    """Files exceeding 10 MB must be rejected with 413."""
    big_content = b"x" * (10 * 1024 * 1024 + 1)
    resp = await auth_client.post(
        "/api/chat/extract-file",
        files={"file": ("large.txt", big_content, "text/plain")},
    )
    assert resp.status_code == 413


@pytest.mark.anyio
async def test_upload_requires_auth(client):
    """Unauthenticated requests must be rejected with 401."""
    resp = await client.post(
        "/api/chat/extract-file",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 401
