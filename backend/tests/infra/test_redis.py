from app.infra.redis import get_redis_url


def test_get_redis_url_returns_configured_url():
    """应返回配置中的 Redis URL。"""
    url = get_redis_url()
    assert url.startswith("redis://")
