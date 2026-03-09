"""
安全工具模块

提供密码哈希、JWT token 签发/验证、API Key 对称加密等核心安全功能。
"""

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from cryptography.fernet import Fernet

from app.core.config import settings

# ---------------------------------------------------------------------------
# 密码哈希（bcrypt）
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希。调用前需确保密码不超过 72 字节。"""
    # bcrypt 4.0+ raises ValueError for passwords exceeding 72 bytes (no silent
    # truncation). The API layer enforces max 72 bytes before reaching this call.
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码是否匹配已存储的 bcrypt 哈希。哈希格式无效时返回 False。"""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT Token
# ---------------------------------------------------------------------------


def create_access_token(user_id: str) -> str:
    """签发 JWT access token，payload 包含 sub(user_id) 和 exp(过期时间)。"""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> str:
    """验证并解码 JWT token，返回 user_id。token 无效或过期时抛出异常。"""
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    return str(payload["sub"])


# ---------------------------------------------------------------------------
# API Key 对称加密（Fernet）
# ---------------------------------------------------------------------------


def _get_fernet() -> Fernet:
    """获取 Fernet 加密实例。ENCRYPTION_KEY 必须是合法的 Fernet key。"""
    return Fernet(settings.encryption_key.encode())


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


def _normalize_keys(raw: str | list[str]) -> list[str]:
    """Normalize API key value to a list (backward compat)."""
    if isinstance(raw, str):
        return [raw] if raw else []
    return [k for k in raw if k]


def resolve_api_keys(provider: str, raw_keys: dict) -> list[str]:
    """Resolve API keys for a provider. Returns a list of keys.

    Priority: user keys first, then server-level key appended.
    """
    decrypted = decrypt_api_keys(raw_keys)
    user_keys = _normalize_keys(decrypted.get(provider, ""))
    fallback: str = getattr(settings, f"{provider}_api_key", "")
    if fallback and fallback not in user_keys:
        user_keys.append(fallback)
    return user_keys


def resolve_api_key(provider: str, raw_keys: dict) -> str:
    """Resolve a single API key (first available). Backward-compatible wrapper."""
    keys = resolve_api_keys(provider, raw_keys)
    return keys[0] if keys else ""


# ---------------------------------------------------------------------------
# API 密钥管理 (Internal PATs)
# ---------------------------------------------------------------------------


def generate_api_key() -> str:
    """生成一个安全的随机 API 密钥（前缀为 jv_）。"""
    return f"jv_{secrets.token_urlsafe(48)}"


def hash_api_key(raw_token: str) -> str:
    """使用 sha256 对原始密钥进行哈希处理。"""
    return hashlib.sha256(raw_token.encode()).hexdigest()
