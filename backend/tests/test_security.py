from app.core.security import hash_password, verify_password


def test_hash_password_produces_bcrypt_hash() -> None:
    hashed = hash_password("my_password")
    assert hashed.startswith("$2b$")


def test_verify_password_correct() -> None:
    hashed = hash_password("my_password")
    assert verify_password("my_password", hashed) is True


def test_verify_password_wrong() -> None:
    hashed = hash_password("my_password")
    assert verify_password("wrong_password", hashed) is False


def test_verify_password_malformed_hash_returns_false() -> None:
    assert verify_password("any_password", "not-a-bcrypt-hash") is False


def test_hash_password_unicode_at_72_byte_limit() -> None:
    # 18 emoji × 4 bytes = 72 bytes exactly — bcrypt's max
    password = "\U0001f600" * 18
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True
