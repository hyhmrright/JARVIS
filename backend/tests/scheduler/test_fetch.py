# backend/tests/scheduler/test_fetch.py
import pytest

from app.scheduler.fetch import sanitize_http_headers, validate_fetch_url


# --- validate_fetch_url ---

def test_valid_public_url():
    validate_fetch_url("https://example.com/page")  # must not raise


def test_blocks_loopback():
    with pytest.raises(ValueError, match="blocked"):
        validate_fetch_url("http://127.0.0.1/admin")


def test_blocks_private_10():
    with pytest.raises(ValueError, match="blocked"):
        validate_fetch_url("http://10.0.0.1/secret")


def test_blocks_private_192():
    with pytest.raises(ValueError, match="blocked"):
        validate_fetch_url("http://192.168.1.1/")


def test_blocks_link_local():
    with pytest.raises(ValueError, match="blocked"):
        validate_fetch_url("http://169.254.169.254/latest/meta-data/")


def test_blocks_non_http_scheme():
    with pytest.raises(ValueError, match="scheme"):
        validate_fetch_url("ftp://example.com/file")


# --- sanitize_http_headers ---

def test_strips_host_header():
    result = sanitize_http_headers({"Host": "evil.com", "Authorization": "Bearer x"})
    assert "Host" not in result
    assert result.get("Authorization") == "Bearer x"


def test_strips_forwarded_headers():
    headers = {
        "X-Forwarded-For": "1.2.3.4",
        "X-Forwarded-Host": "evil.com",
        "X-Real-IP": "1.2.3.4",
        "Cookie": "session=abc",
    }
    result = sanitize_http_headers(headers)
    assert "X-Forwarded-For" not in result
    assert "X-Forwarded-Host" not in result
    assert "X-Real-IP" not in result
    assert result["Cookie"] == "session=abc"


def test_empty_headers():
    assert sanitize_http_headers({}) == {}
