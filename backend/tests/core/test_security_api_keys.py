import hashlib

from app.core.security import generate_api_key, hash_api_key


def test_generate_api_key() -> None:
    # 1. 生成密钥
    raw_token = generate_api_key()

    # 2. 验证格式
    assert raw_token.startswith("jv_")
    assert len(raw_token) >= 48

    # 3. 验证随机性
    raw_token_2 = generate_api_key()
    assert raw_token != raw_token_2


def test_hash_api_key() -> None:
    # 1. 提供原始密钥
    raw_token = "jv_test_token_123"

    # 2. 执行哈希
    key_hash = hash_api_key(raw_token)

    # 3. 验证哈希正确性
    expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    assert key_hash == expected_hash
