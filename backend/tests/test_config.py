from app.core.config import settings


def test_settings_loads():
    assert settings.database_url is not None
    assert settings.jwt_secret is not None
    assert settings.redis_url is not None
