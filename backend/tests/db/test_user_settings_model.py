# backend/tests/db/test_user_settings_model.py
import uuid
from unittest.mock import MagicMock


def test_user_settings_get_api_key_returns_none_when_missing():
    """get_api_key() must return None when the key for a provider is not set."""
    from app.db.models import UserSettings

    us = UserSettings(user_id=uuid.uuid4(), api_keys={})
    mock_fernet = MagicMock()

    result = us.get_api_key("openai", mock_fernet)
    assert result is None
    mock_fernet.decrypt.assert_not_called()


def test_user_settings_get_api_key_decrypts_stored_key():
    """get_api_key() must decrypt and return the stored key."""
    from app.db.models import UserSettings

    us = UserSettings(user_id=uuid.uuid4(), api_keys={"openai": "encrypted_blob"})
    mock_fernet = MagicMock()
    mock_fernet.decrypt.return_value = b"sk-openai-real"

    result = us.get_api_key("openai", mock_fernet)
    assert result == "sk-openai-real"
    mock_fernet.decrypt.assert_called_once_with(b"encrypted_blob")


def test_user_settings_set_api_key_encrypts_and_stores():
    """set_api_key() must encrypt and store the key in api_keys."""
    from app.db.models import UserSettings

    us = UserSettings(user_id=uuid.uuid4(), api_keys={})
    mock_fernet = MagicMock()
    mock_fernet.encrypt.return_value = b"encrypted_result"

    us.set_api_key("deepseek", "sk-ds-key", mock_fernet)

    assert us.api_keys.get("deepseek") == "encrypted_result"
    mock_fernet.encrypt.assert_called_once_with(b"sk-ds-key")
