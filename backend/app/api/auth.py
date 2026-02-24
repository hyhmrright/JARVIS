from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User, UserSettings
from app.db.session import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _validate_password_bytes(v: str) -> str:
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


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("3/minute")
async def register(
    request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    await db.flush()
    db.add(UserSettings(user_id=user.id))
    await db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(str(user.id)))
