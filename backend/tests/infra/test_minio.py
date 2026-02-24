from app.infra.minio import get_minio_client


def test_get_minio_client_returns_client():
    """get_minio_client 应返回有效的 Minio 实例。"""
    client = get_minio_client()
    assert client is not None
    assert hasattr(client, "put_object")
    assert hasattr(client, "bucket_exists")
