from app.core.config import settings


def get_redis_url() -> str:
    return settings.redis_url
