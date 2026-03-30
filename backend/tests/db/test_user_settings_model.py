# backend/tests/db/test_user_settings_model.py
import uuid
from unittest.mock import patch


def test_user_settings_get_api_key_returns_none_when_missing():
    """get_api_key() must return None when the key for a provider is not set."""
    from app.db.models import UserSettings

    us = UserSettings(user_id=uuid.uuid4(), api_keys={})
    with patch("app.core.security.decrypt_api_keys", return_value={}):
        result = us.get_api_key("openai")
    assert result is None


def test_user_settings_get_api_key_returns_decrypted_key():
    """get_api_key() must return the decrypted key from the stored dict."""
    from app.db.models import UserSettings

    us = UserSettings(user_id=uuid.uuid4(), api_keys={"__encrypted__": "blob"})
    with patch(
        "app.core.security.decrypt_api_keys",
        return_value={"openai": "sk-openai-real"},
    ):
        result = us.get_api_key("openai")
    assert result == "sk-openai-real"


def test_user_settings_set_api_key_re_encrypts_dict():
    """set_api_key() must decrypt, set the key, then re-encrypt the whole dict."""
    from app.db.models import UserSettings

    us = UserSettings(user_id=uuid.uuid4(), api_keys={"__encrypted__": "old_blob"})
    with (
        patch(
            "app.core.security.decrypt_api_keys",
            return_value={"anthropic": "sk-ant-old"},
        ) as mock_dec,
        patch(
            "app.core.security.encrypt_api_keys",
            return_value={"__encrypted__": "new_blob"},
        ) as mock_enc,
    ):
        us.set_api_key("deepseek", "sk-ds-new")

    mock_dec.assert_called_once()
    mock_enc.assert_called_once_with(
        {"anthropic": "sk-ant-old", "deepseek": "sk-ds-new"}
    )
    assert us.api_keys == {"__encrypted__": "new_blob"}
