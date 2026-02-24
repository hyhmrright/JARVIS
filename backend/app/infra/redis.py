from app.core.config import settings


def get_redis_url() -> str:
    """返回配置中的 Redis 连接 URL。"""
    return settings.redis_url
