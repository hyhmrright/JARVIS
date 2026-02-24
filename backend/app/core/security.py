import base64
import binascii
import json
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from cryptography.fernet import Fernet

from app.core.config import settings


def hash_password(password: str) -> str:
    # bcrypt 4.0+ raises ValueError for passwords exceeding 72 bytes (no silent
    # truncation). The API layer enforces max 72 bytes before reaching this call.
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(user_id: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> str:
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    return str(payload["sub"])


def _get_fernet() -> Fernet:
    key = settings.encryption_key.encode()
    try:
        return Fernet(key)
    except (ValueError, binascii.Error):
        padded = base64.urlsafe_b64encode(key[:32].ljust(32, b"\x00"))
        return Fernet(padded)


def encrypt_api_keys(api_keys: dict) -> dict:
    """将 api_keys 字典中的所有值加密后返回新字典。"""
    encrypted = _get_fernet().encrypt(json.dumps(api_keys).encode()).decode()
    return {"__encrypted__": encrypted}


def decrypt_api_keys(stored: dict) -> dict:
    """解密 api_keys 字典。若不是加密格式则原样返回（兼容旧数据）。"""
    if "__encrypted__" not in stored:
        return stored
    decrypted = _get_fernet().decrypt(stored["__encrypted__"].encode())
    return json.loads(decrypted)
