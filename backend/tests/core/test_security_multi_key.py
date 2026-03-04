"""Tests for multi-API-key support in security module."""

import pytest

from app.core.security import (
    _normalize_keys,
    decrypt_api_keys,
    encrypt_api_keys,
    resolve_api_key,
    resolve_api_keys,
)


def test_normalize_keys_string() -> None:
    assert _normalize_keys("sk-abc") == ["sk-abc"]


def test_normalize_keys_empty_string() -> None:
    assert _normalize_keys("") == []


def test_normalize_keys_list() -> None:
    assert _normalize_keys(["sk-1", "sk-2"]) == ["sk-1", "sk-2"]


def test_normalize_keys_list_filters_empty() -> None:
    assert _normalize_keys(["sk-1", "", "sk-2"]) == ["sk-1", "sk-2"]


def test_encrypt_decrypt_multi_key() -> None:
    raw = {"deepseek": ["sk-1", "sk-2"], "openai": ["sk-abc"]}
    encrypted = encrypt_api_keys(raw)
    assert "__encrypted__" in encrypted
    decrypted = decrypt_api_keys(encrypted)
    assert decrypted == raw


def test_encrypt_decrypt_backward_compat() -> None:
    """Old format (single string values) still works."""
    raw = {"deepseek": "sk-old"}
    encrypted = encrypt_api_keys(raw)
    decrypted = decrypt_api_keys(encrypted)
    assert decrypted == raw


def test_resolve_api_keys_multi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.security.settings.deepseek_api_key", "")
    raw = {"deepseek": ["sk-1", "sk-2"]}
    encrypted = encrypt_api_keys(raw)
    keys = resolve_api_keys("deepseek", encrypted)
    assert keys == ["sk-1", "sk-2"]


def test_resolve_api_keys_with_server_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.core.security.settings.openai_api_key", "sk-server")
    raw = {"openai": ["sk-user"]}
    encrypted = encrypt_api_keys(raw)
    keys = resolve_api_keys("openai", encrypted)
    assert keys == ["sk-user", "sk-server"]


def test_resolve_api_keys_server_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.security.settings.openai_api_key", "sk-server")
    keys = resolve_api_keys("openai", {})
    assert keys == ["sk-server"]


def test_resolve_api_keys_no_duplicate_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Server key should not be duplicated if user already has it."""
    monkeypatch.setattr("app.core.security.settings.deepseek_api_key", "sk-same")
    raw = {"deepseek": ["sk-same"]}
    encrypted = encrypt_api_keys(raw)
    keys = resolve_api_keys("deepseek", encrypted)
    assert keys == ["sk-same"]


def test_resolve_api_key_backward_compat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Old resolve_api_key (singular) returns first key."""
    monkeypatch.setattr("app.core.security.settings.deepseek_api_key", "")
    raw = {"deepseek": ["sk-1", "sk-2"]}
    encrypted = encrypt_api_keys(raw)
    key = resolve_api_key("deepseek", encrypted)
    assert key == "sk-1"


def test_resolve_api_key_old_format_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Old single-string format still works with resolve_api_keys."""
    monkeypatch.setattr("app.core.security.settings.deepseek_api_key", "")
    raw = {"deepseek": "sk-old-single"}
    encrypted = encrypt_api_keys(raw)
    keys = resolve_api_keys("deepseek", encrypted)
    assert keys == ["sk-old-single"]
