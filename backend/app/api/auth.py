"""
认证 API 路由（注册 / 登录）

HTTP 状态码说明（前端依赖这些状态码显示对应的中文提示）：
  201 → 注册成功（由 register 端点返回）
  200 → 登录成功（由 login 端点返回）
  409 → 邮箱已注册（由 register 端点返回）
  401 → 邮箱或密码错误（由 login 端点返回）
  422 → 请求体校验失败（Pydantic 自动返回）
  429 → 速率限制超出（slowapi 自动返回）
"""

import asyncio

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.audit import log_action
from app.core.limiter import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User, UserSettings
from app.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _validate_password_bytes(v: str) -> str:
    """bcrypt 要求密码不超过 72 字节，在校验层提前拦截。"""
    if len(v.encode()) > 72:
        raise ValueError("password must not exceed 72 bytes when UTF-8 encoded")
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str | None = None

    _check_bytes = field_validator("password")(_validate_password_bytes)


class LoginRequest(BaseModel):
    email: EmailStr
    # min_length=1 intentionally differs from RegisterRequest(8): login must
    # accept any stored password regardless of current registration policy.
    password: str = Field(min_length=1)

    _check_bytes = field_validator("password")(_validate_password_bytes)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    display_name: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)

    _check_current_bytes = field_validator("current_password")(_validate_password_bytes)
    _check_new_bytes = field_validator("new_password")(_validate_password_bytes)


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("3/minute")
async def register(
    request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """注册新用户，成功后返回 JWT token（自动登录）。"""
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=body.email,
        password_hash=await asyncio.to_thread(hash_password, body.password),
        display_name=body.display_name,
    )
    db.add(user)
    await db.flush()  # flush 以获取 user.id，用于创建关联的 UserSettings
    db.add(UserSettings(user_id=user.id))
    await db.commit()
    logger.info("user_registered", user_id=str(user.id), email=body.email)
    await log_action("user.register", user_id=user.id, request=request)
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        role=user.role,
        display_name=user.display_name,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """验证邮箱和密码，成功后返回 JWT token。"""
    user = await db.scalar(select(User).where(User.email == body.email))
    password_ok = user is not None and await asyncio.to_thread(
        verify_password, body.password, user.password_hash
    )
    if not password_ok:
        # 统一返回 401，不区分"用户不存在"和"密码错误"以防枚举攻击
        logger.warning("login_failed", email=body.email)
        # Record user_id when the account exists (does not leak enumeration to caller).
        await log_action(
            "user.login_failed",
            user_id=user.id if user else None,
            # Storing the attempted email is intentional for forensic
            # correlation; it is admin-only and never returned to the caller.
            extra={"email": body.email},
            request=request,
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    assert user is not None  # narrowing: password_ok=True implies user was found
    logger.info("login_success", user_id=str(user.id), email=user.email)
    await log_action("user.login", user_id=user.id, request=request)
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        role=user.role,
        display_name=user.display_name,
    )


@router.post("/change-password", status_code=204)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """修改当前用户密码。需验证旧密码后才可设置新密码。"""
    current_ok = await asyncio.to_thread(
        verify_password, body.current_password, user.password_hash
    )
    if not current_ok:
        await log_action(
            "user.change_password_failed", user_id=user.id, request=request
        )
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = await asyncio.to_thread(hash_password, body.new_password)
    await db.commit()
    logger.info("password_changed", user_id=str(user.id))
    await log_action("user.change_password", user_id=user.id, request=request)
