# Jarvis 个人助手系统实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建多用户 AI 个人助手 Web 应用，支持通用对话、工具调用、RAG 知识库，用户数据完全隔离。

**Architecture:** 单体 LangGraph Agent 图作为核心，FastAPI 提供 REST + SSE 接口，Vue 3 前端通过流式接口展示对话。PostgreSQL 存用户/对话数据，Qdrant 存向量（按用户 namespace 隔离），MinIO 存原始文件，Redis 做会话缓存。

**Tech Stack:** Python 3.13 + FastAPI + LangGraph + LangChain，Vue 3 + TypeScript + Vite（Bun），postgres:18.2-bookworm，qdrant/qdrant:v1.17.0，redis:8.6.0-alpine3.23，minio/minio:RELEASE.2025-09-07T16-13-09Z，oven/bun:1.3.9。

---

## Phase 1：基础设施

### Task 1：项目目录结构 + Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `backend/pyproject.toml`
- Create: `.env.example`

**Step 1：创建项目目录骨架**

```bash
mkdir -p backend/app/{api,agent,tools,rag,db,core}
mkdir -p backend/tests/{api,agent,tools,rag}
mkdir -p frontend/src/{pages,components,stores,api}
touch backend/app/__init__.py
touch backend/app/api/__init__.py
touch backend/app/agent/__init__.py
touch backend/app/tools/__init__.py
touch backend/app/rag/__init__.py
touch backend/app/db/__init__.py
touch backend/app/core/__init__.py
```

**Step 2：创建 `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:18.2-bookworm
    environment:
      POSTGRES_DB: jarvis
      POSTGRES_USER: jarvis
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U jarvis"]
      interval: 5s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:v1.17.0
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "6333:6333"
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:6333/health || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:8.6.0-alpine3.23
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:RELEASE.2025-09-07T16-13-09Z
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9000/minio/health/live || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://jarvis:${POSTGRES_PASSWORD}@postgres:5432/jarvis
      REDIS_URL: redis://redis:6379
      QDRANT_URL: http://qdrant:6333
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      JWT_SECRET: ${JWT_SECRET}
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  postgres_data:
  qdrant_data:
  redis_data:
  minio_data:
```

**Step 3：创建 `.env.example`**

```bash
POSTGRES_PASSWORD=changeme
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=changeme123
JWT_SECRET=your-secret-key-change-in-production
DEEPSEEK_API_KEY=your-deepseek-api-key
```

**Step 4：创建 `backend/Dockerfile`**

```dockerfile
FROM python:3.13.12-slim-bookworm

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen

COPY . .

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

**Step 5：创建 `frontend/Dockerfile`**

```dockerfile
FROM oven/bun:1.3.9

WORKDIR /app

COPY package.json bun.lockb* ./
RUN bun install --frozen-lockfile

COPY . .

CMD ["bun", "run", "dev", "--host", "0.0.0.0"]
```

**Step 6：初始化后端 `pyproject.toml`**

```toml
[project]
name = "jarvis-backend"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.12",
    "langgraph>=1.0.5",
    "langchain-core>=1.2.7",
    "langchain-deepseek>=1.0.1",
    "langchain-openai>=0.3.0",
    "langchain-anthropic>=0.3.0",
    "qdrant-client>=1.12.0",
    "redis[hiredis]>=5.2.0",
    "minio>=7.2.0",
    "pypdf>=5.0.0",
    "python-docx>=1.1.0",
    "tiktoken>=0.8.0",
    "httpx>=0.28.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "httpx>=0.28.0",
    "ruff>=0.8.0",
    "pyright>=1.1.390",
]

[tool.ruff]
line-length = 88
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 7：提交**

```bash
git add docker-compose.yml backend/ frontend/ .env.example
git commit -m "feat: project structure and docker compose"
git push
```

---

### Task 2：后端配置与数据库连接

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Test: `backend/tests/test_config.py`

**Step 1：写失败测试**

```python
# backend/tests/test_config.py
from app.core.config import settings

def test_settings_loads():
    assert settings.database_url is not None
    assert settings.jwt_secret is not None
    assert settings.redis_url is not None
```

**Step 2：运行测试确认失败**

```bash
cd backend && uv run pytest tests/test_config.py -v
# Expected: FAIL - ModuleNotFoundError: app.core.config
```

**Step 3：实现 `backend/app/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis"
    redis_url: str = "redis://localhost:6379"
    qdrant_url: str = "http://localhost:6333"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "changeme123"
    minio_bucket: str = "jarvis-documents"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days


settings = Settings()
```

**Step 4：实现 `backend/app/db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

**Step 5：实现 `backend/app/db/session.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

**Step 6：运行测试确认通过**

```bash
uv run pytest tests/test_config.py -v
# Expected: PASS
```

**Step 7：提交**

```bash
git add backend/app/core/ backend/app/db/ backend/tests/
git commit -m "feat: app config and database session"
git push
```

---

## Phase 2：数据库 Schema + 迁移

### Task 3：SQLAlchemy 模型 + Alembic 迁移

**Files:**
- Create: `backend/app/db/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/001_initial.py`
- Test: `backend/tests/db/test_models.py`

**Step 1：写失败测试**

```python
# backend/tests/db/test_models.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.db.models import User, Conversation, Message, Document, UserSettings
from app.db.base import Base

TEST_DB = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def session():
    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s

async def test_create_user(session):
    user = User(email="test@example.com", password_hash="hashed")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    assert user.id is not None
    assert user.is_active is True

async def test_user_has_settings_cascade(session):
    user = User(email="a@b.com", password_hash="x")
    settings = UserSettings(user=user)
    session.add(user)
    await session.commit()
    assert settings.model_provider == "deepseek"
```

**Step 2：运行确认失败**

```bash
uv add aiosqlite --group dev
uv run pytest tests/db/test_models.py -v
# Expected: FAIL - cannot import name 'User'
```

**Step 3：实现 `backend/app/db/models.py`**

```python
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    settings: Mapped["UserSettings"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="deepseek")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="deepseek-chat")
    api_keys: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    enabled_tools: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=lambda: ["search", "code_exec", "file", "datetime"])
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="settings")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New Conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (CheckConstraint("role IN ('human', 'ai', 'tool', 'system')", name="ck_messages_role"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    model_provider: Mapped[str | None] = mapped_column(String(50))
    model_name: Mapped[str | None] = mapped_column(String(100))
    tokens_input: Mapped[int | None] = mapped_column(Integer)
    tokens_output: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (CheckConstraint("file_type IN ('pdf', 'txt', 'md', 'docx')", name="ck_documents_file_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qdrant_collection: Mapped[str] = mapped_column(String(255), nullable=False)
    minio_object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="documents")
```

**Step 4：初始化 Alembic**

```bash
cd backend && uv run alembic init alembic
```

修改 `backend/alembic/env.py` 中的 `target_metadata`：

```python
# 在 env.py 顶部添加
from app.db.base import Base
from app.db import models  # noqa: F401 确保模型被注册

target_metadata = Base.metadata
```

修改 `backend/alembic.ini` 的 `sqlalchemy.url`：
```
sqlalchemy.url = postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis
```

**Step 5：生成初始迁移**

```bash
uv run alembic revision --autogenerate -m "initial schema"
# Expected: 生成 alembic/versions/xxxx_initial_schema.py
```

**Step 6：运行测试确认通过**

```bash
uv run pytest tests/db/test_models.py -v
# Expected: PASS
```

**Step 7：提交**

```bash
git add backend/app/db/models.py backend/alembic* backend/tests/db/
git commit -m "feat: database models and alembic migrations"
git push
```

---

## Phase 3：用户认证

### Task 4：注册 / 登录 API（JWT）

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/app/api/auth.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/api/test_auth.py`

**Step 1：写失败测试**

```python
# backend/tests/api/test_auth.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_register_success(client):
    resp = await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "password123",
        "display_name": "Test User"
    })
    assert resp.status_code == 201
    assert "access_token" in resp.json()

async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "pass123"}
    await client.post("/api/auth/register", json=payload)
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409

async def test_login_success(client):
    await client.post("/api/auth/register", json={"email": "login@example.com", "password": "pass123"})
    resp = await client.post("/api/auth/login", json={"email": "login@example.com", "password": "pass123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={"email": "wp@example.com", "password": "correct"})
    resp = await client.post("/api/auth/login", json={"email": "wp@example.com", "password": "wrong"})
    assert resp.status_code == 401
```

**Step 2：运行确认失败**

```bash
uv run pytest tests/api/test_auth.py -v
# Expected: FAIL
```

**Step 3：实现 `backend/app/core/security.py`**

```python
from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return payload["sub"]
```

**Step 4：实现 `backend/app/api/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password, verify_password, create_access_token
from app.db.models import User, UserSettings
from app.db.session import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=body.email, password_hash=hash_password(body.password), display_name=body.display_name)
    db.add(user)
    await db.flush()
    db.add(UserSettings(user_id=user.id))
    await db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(str(user.id)))
```

**Step 5：实现 `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router

app = FastAPI(title="Jarvis API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 6：运行测试确认通过**

```bash
uv run pytest tests/api/test_auth.py -v
# Expected: 4 passed
```

**Step 7：提交**

```bash
git add backend/app/core/security.py backend/app/api/ backend/app/main.py backend/tests/api/
git commit -m "feat: user registration and login with JWT"
git push
```

---

### Task 5：当前用户依赖 + 对话 CRUD API

**Files:**
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/conversations.py`
- Test: `backend/tests/api/test_conversations.py`

**Step 1：写失败测试**

```python
# backend/tests/api/test_conversations.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def auth_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/auth/register", json={"email": "conv@test.com", "password": "pass123"})
        token = resp.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c

async def test_create_conversation(auth_client):
    resp = await auth_client.post("/api/conversations", json={"title": "My Chat"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "My Chat"

async def test_list_conversations(auth_client):
    await auth_client.post("/api/conversations", json={"title": "Chat 1"})
    await auth_client.post("/api/conversations", json={"title": "Chat 2"})
    resp = await auth_client.get("/api/conversations")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2

async def test_delete_conversation(auth_client):
    create = await auth_client.post("/api/conversations", json={"title": "To Delete"})
    conv_id = create.json()["id"]
    resp = await auth_client.delete(f"/api/conversations/{conv_id}")
    assert resp.status_code == 204
```

**Step 2：运行确认失败**

```bash
uv run pytest tests/api/test_conversations.py -v
# Expected: FAIL
```

**Step 3：实现 `backend/app/api/deps.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        user_id = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = await db.scalar(select(User).where(User.id == user_id, User.is_active == True))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

**Step 4：实现 `backend/app/api/conversations.py`**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.models import Conversation, User
from app.db.session import get_db

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    title: str = "New Conversation"


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    model_config = {"from_attributes": True}


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = Conversation(user_id=user.id, title=body.title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc()))
    return rows.all()


@router.delete("/{conv_id}", status_code=204)
async def delete_conversation(
    conv_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.scalar(select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id))
    if not conv:
        raise HTTPException(status_code=404)
    await db.delete(conv)
    await db.commit()
```

**Step 5：在 `main.py` 注册路由**

```python
# 在 app.include_router(auth_router) 后追加
from app.api.conversations import router as conversations_router
app.include_router(conversations_router)
```

**Step 6：运行测试确认通过**

```bash
uv run pytest tests/api/test_conversations.py -v
# Expected: 3 passed
```

**Step 7：提交**

```bash
git add backend/app/api/ backend/tests/api/
git commit -m "feat: conversation CRUD API with JWT auth"
git push
```

---

## Phase 4：LangGraph Agent 核心

### Task 6：基础对话 Agent（DeepSeek，流式输出）

**Files:**
- Create: `backend/app/agent/state.py`
- Create: `backend/app/agent/llm.py`
- Create: `backend/app/agent/graph.py`
- Create: `backend/app/api/chat.py`
- Test: `backend/tests/agent/test_graph.py`

**Step 1：写失败测试**

```python
# backend/tests/agent/test_graph.py
import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import AIMessage, HumanMessage
from app.agent.graph import create_graph

async def test_graph_returns_ai_message():
    graph = create_graph(provider="deepseek", model="deepseek-chat", api_key="test")
    mock_response = AIMessage(content="Hello!")
    with patch("app.agent.llm.get_llm") as mock_llm:
        mock_instance = AsyncMock()
        mock_instance.ainvoke.return_value = mock_response
        mock_llm.return_value = mock_instance
        result = await graph.ainvoke({"messages": [HumanMessage(content="Hi")]})
    assert result["messages"][-1].content == "Hello!"
```

**Step 2：运行确认失败**

```bash
uv run pytest tests/agent/test_graph.py -v
# Expected: FAIL
```

**Step 3：实现 `backend/app/agent/state.py`**

```python
from dataclasses import dataclass, field
from typing import Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


@dataclass(kw_only=True)
class AgentState:
    messages: Annotated[list[BaseMessage], add_messages] = field(default_factory=list)
```

**Step 4：实现 `backend/app/agent/llm.py`**

```python
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic


def get_llm(provider: str, model: str, api_key: str) -> BaseChatModel:
    match provider:
        case "deepseek":
            return ChatDeepSeek(model=model, api_key=api_key)
        case "openai":
            return ChatOpenAI(model=model, api_key=api_key)
        case "anthropic":
            return ChatAnthropic(model=model, api_key=api_key)
        case _:
            raise ValueError(f"Unknown provider: {provider}")
```

**Step 5：实现 `backend/app/agent/graph.py`**

```python
from typing import Any
from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph
from app.agent.llm import get_llm
from app.agent.state import AgentState


def create_graph(provider: str, model: str, api_key: str) -> Any:
    llm = get_llm(provider, model, api_key)

    async def call_llm(state: AgentState) -> dict[str, list[BaseMessage]]:
        response = await llm.ainvoke(state.messages)
        return {"messages": [response]}

    graph: StateGraph[AgentState] = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_edge(START, "llm")
    graph.add_edge("llm", END)
    return graph.compile()
```

**Step 6：实现 `backend/app/api/chat.py`（SSE 流式接口）**

```python
import json
import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage
from app.agent.graph import create_graph
from app.agent.state import AgentState
from app.api.deps import get_current_user
from app.db.models import Conversation, Message, User, UserSettings
from app.db.session import get_db

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID
    content: str


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.scalar(select(Conversation).where(Conversation.id == body.conversation_id, Conversation.user_id == user.id))
    if not conv:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)

    user_settings = await db.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    provider = user_settings.model_provider if user_settings else "deepseek"
    model_name = user_settings.model_name if user_settings else "deepseek-chat"
    api_keys = user_settings.api_keys if user_settings else {}
    api_key = api_keys.get(provider, "")

    # 保存用户消息
    db.add(Message(conversation_id=conv.id, role="human", content=body.content))
    await db.commit()

    # 加载历史消息
    history = await db.scalars(select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at))
    lc_messages = []
    for msg in history.all():
        if msg.role == "human":
            lc_messages.append(HumanMessage(content=msg.content))

    async def generate():
        graph = create_graph(provider=provider, model=model_name, api_key=api_key)
        full_content = ""
        async for chunk in graph.astream(AgentState(messages=lc_messages)):
            if "llm" in chunk:
                ai_msg = chunk["llm"]["messages"][-1]
                full_content = ai_msg.content
                yield f"data: {json.dumps({'content': full_content})}\n\n"
        # 保存 AI 消息
        async with db.begin():
            db.add(Message(conversation_id=conv.id, role="ai", content=full_content, model_provider=provider, model_name=model_name))

    return StreamingResponse(generate(), media_type="text/event-stream")
```

**Step 7：注册路由到 `main.py`**

```python
from app.api.chat import router as chat_router
app.include_router(chat_router)
```

**Step 8：运行测试确认通过**

```bash
uv run pytest tests/agent/test_graph.py -v
# Expected: PASS
```

**Step 9：提交**

```bash
git add backend/app/agent/ backend/app/api/chat.py backend/tests/agent/
git commit -m "feat: LangGraph agent with streaming SSE chat endpoint"
git push
```

---

## Phase 5：工具调用

### Task 7：工具框架 + 4 个内置工具

**Files:**
- Create: `backend/app/tools/datetime_tool.py`
- Create: `backend/app/tools/search_tool.py`
- Create: `backend/app/tools/code_exec_tool.py`
- Create: `backend/app/tools/file_tool.py`
- Modify: `backend/app/agent/graph.py`（绑定工具）
- Test: `backend/tests/tools/test_tools.py`

**Step 1：写失败测试**

```python
# backend/tests/tools/test_tools.py
import pytest
from app.tools.datetime_tool import get_datetime
from app.tools.code_exec_tool import execute_code

def test_datetime_returns_string():
    result = get_datetime.invoke({})
    assert isinstance(result, str)
    assert "2" in result  # 年份包含 2

async def test_code_exec_simple():
    result = await execute_code.ainvoke({"code": "print(1 + 1)"})
    assert "2" in result

async def test_code_exec_timeout():
    result = await execute_code.ainvoke({"code": "import time; time.sleep(60)"})
    assert "timeout" in result.lower()
```

**Step 2：运行确认失败**

```bash
uv run pytest tests/tools/test_tools.py -v
# Expected: FAIL
```

**Step 3：实现工具**

```python
# backend/app/tools/datetime_tool.py
from datetime import datetime, timezone
from langchain_core.tools import tool

@tool
def get_datetime() -> str:
    """获取当前日期和时间（UTC）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
```

```python
# backend/app/tools/search_tool.py
import httpx
from langchain_core.tools import tool

@tool
async def web_search(query: str) -> str:
    """搜索互联网获取最新信息。query 为搜索关键词。"""
    # 使用 DuckDuckGo Instant Answer API（无需 API Key）
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1},
            timeout=10.0,
        )
    data = resp.json()
    abstract = data.get("AbstractText", "")
    related = [r.get("Text", "") for r in data.get("RelatedTopics", [])[:3]]
    return abstract or "\n".join(related) or "No results found."
```

```python
# backend/app/tools/code_exec_tool.py
import asyncio
from langchain_core.tools import tool

@tool
async def execute_code(code: str) -> str:
    """在沙箱中执行 Python 代码并返回输出。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        if stderr:
            return f"Error: {stderr.decode()}"
        return stdout.decode() or "(no output)"
    except asyncio.TimeoutError:
        return "Timeout: code execution exceeded 30 seconds"
```

```python
# backend/app/tools/file_tool.py
from langchain_core.tools import tool

@tool
def read_file(path: str, user_id: str) -> str:
    """读取用户私有文件内容。path 为文件名，user_id 为用户ID。"""
    import pathlib
    safe_path = pathlib.Path(f"/tmp/jarvis/{user_id}") / pathlib.Path(path).name
    if not safe_path.exists():
        return f"File not found: {path}"
    return safe_path.read_text(encoding="utf-8")

@tool
def write_file(path: str, content: str, user_id: str) -> str:
    """写入内容到用户私有文件。"""
    import pathlib
    dir_path = pathlib.Path(f"/tmp/jarvis/{user_id}")
    dir_path.mkdir(parents=True, exist_ok=True)
    safe_path = dir_path / pathlib.Path(path).name
    safe_path.write_text(content, encoding="utf-8")
    return f"File written: {path}"
```

**Step 4：更新 `backend/app/agent/graph.py` 绑定工具**

```python
# 在 create_graph 中，llm 创建后添加：
from app.tools.datetime_tool import get_datetime
from app.tools.search_tool import web_search
from app.tools.code_exec_tool import execute_code
from langgraph.prebuilt import ToolNode

tools = [get_datetime, web_search, execute_code]
llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)

# 替换 call_llm 并添加条件边
async def call_llm(state: AgentState) -> dict:
    response = await llm_with_tools.ainvoke(state.messages)
    return {"messages": [response]}

def should_use_tool(state: AgentState) -> str:
    last = state.messages[-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END

graph.add_node("llm", call_llm)
graph.add_node("tools", tool_node)
graph.add_edge(START, "llm")
graph.add_conditional_edges("llm", should_use_tool)
graph.add_edge("tools", "llm")
```

**Step 5：运行测试确认通过**

```bash
uv run pytest tests/tools/test_tools.py -v
# Expected: 3 passed
```

**Step 6：提交**

```bash
git add backend/app/tools/ backend/tests/tools/
git commit -m "feat: 4 built-in tools with LangGraph tool node"
git push
```

---

## Phase 6：RAG 模块

### Task 8：文档上传 + Qdrant 向量化

**Files:**
- Create: `backend/app/rag/chunker.py`
- Create: `backend/app/rag/embedder.py`
- Create: `backend/app/rag/indexer.py`
- Create: `backend/app/api/documents.py`
- Test: `backend/tests/rag/test_chunker.py`

**Step 1：写失败测试**

```python
# backend/tests/rag/test_chunker.py
from app.rag.chunker import chunk_text

def test_chunk_text_basic():
    text = "word " * 1000
    chunks = chunk_text(text, chunk_size=200, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 250 for c in chunks)

def test_chunk_preserves_content():
    text = "Hello world. " * 100
    chunks = chunk_text(text)
    combined = " ".join(chunks)
    assert "Hello world" in combined
```

**Step 2：运行确认失败**

```bash
uv run pytest tests/rag/test_chunker.py -v
# Expected: FAIL
```

**Step 3：实现 `backend/app/rag/chunker.py`**

```python
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """将文本切分为固定大小的块，带重叠。"""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks
```

**Step 4：实现 `backend/app/rag/embedder.py`**

```python
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings


def get_embedder(api_key: str):
    # 使用 OpenAI 兼容接口，DeepSeek 也支持
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=api_key,
    )
```

**Step 5：实现 `backend/app/rag/indexer.py`**

```python
import uuid
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from app.core.config import settings
from app.rag.chunker import chunk_text
from app.rag.embedder import get_embedder


async def index_document(
    user_id: str,
    doc_id: str,
    text: str,
    api_key: str,
) -> int:
    client = AsyncQdrantClient(url=settings.qdrant_url)
    collection = f"user_{user_id}"

    # 确保 collection 存在
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if collection not in names:
        await client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )

    chunks = chunk_text(text)
    embedder = get_embedder(api_key)
    vectors = await embedder.aembed_documents(chunks)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={"doc_id": doc_id, "chunk_index": i, "text": chunk},
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors))
    ]
    await client.upsert(collection_name=collection, points=points)
    return len(chunks)


async def search_documents(user_id: str, query: str, api_key: str, top_k: int = 5) -> list[str]:
    client = AsyncQdrantClient(url=settings.qdrant_url)
    collection = f"user_{user_id}"
    embedder = get_embedder(api_key)
    query_vec = await embedder.aembed_query(query)
    results = await client.search(collection_name=collection, query_vector=query_vec, limit=top_k)
    return [r.payload["text"] for r in results if r.payload]
```

**Step 6：实现 `backend/app/api/documents.py`**

```python
import io
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from minio import Minio
from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models import Document, User, UserSettings
from app.db.session import get_db
from app.rag.indexer import index_document
from sqlalchemy import select

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_TYPES = {"pdf": "application/pdf", "txt": "text/plain", "md": "text/markdown", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAX_SIZE = 50 * 1024 * 1024  # 50MB


def extract_text(content: bytes, file_type: str) -> str:
    if file_type in ("txt", "md"):
        return content.decode("utf-8", errors="ignore")
    if file_type == "pdf":
        import pypdf, io
        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    if file_type == "docx":
        import docx, io
        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    return ""


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type .{ext} not supported")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50MB limit")

    # 存入 MinIO
    minio_client = Minio(settings.minio_endpoint, access_key=settings.minio_access_key, secret_key=settings.minio_secret_key, secure=False)
    if not minio_client.bucket_exists(settings.minio_bucket):
        minio_client.make_bucket(settings.minio_bucket)
    object_key = f"{user.id}/{file.filename}"
    minio_client.put_object(settings.minio_bucket, object_key, io.BytesIO(content), len(content))

    # 提取文本并向量化
    user_settings = await db.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    api_key = (user_settings.api_keys or {}).get(user_settings.model_provider, "") if user_settings else ""

    text = extract_text(content, ext)
    doc = Document(
        user_id=user.id,
        filename=file.filename,
        file_type=ext,
        file_size_bytes=len(content),
        qdrant_collection=f"user_{user.id}",
        minio_object_key=object_key,
    )
    db.add(doc)
    await db.flush()
    chunk_count = await index_document(str(user.id), str(doc.id), text, api_key)
    doc.chunk_count = chunk_count
    await db.commit()
    return {"id": str(doc.id), "filename": doc.filename, "chunk_count": chunk_count}
```

**Step 7：注册路由到 `main.py`**

```python
from app.api.documents import router as documents_router
app.include_router(documents_router)
```

**Step 8：运行测试确认通过**

```bash
uv run pytest tests/rag/test_chunker.py -v
# Expected: 2 passed
```

**Step 9：提交**

```bash
git add backend/app/rag/ backend/app/api/documents.py backend/tests/rag/
git commit -m "feat: RAG document upload, chunking, and Qdrant indexing"
git push
```

---

## Phase 7：前端

### Task 9：Vue 3 前端项目初始化

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`

**Step 1：初始化前端项目**

```bash
cd frontend
bun create vite . --template vue-ts
bun add pinia vue-router @vueuse/core axios
bun add -d @types/node
```

**Step 2：配置 `frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    proxy: {
      "/api": { target: "http://backend:8000", changeOrigin: true },
    },
  },
});
```

**Step 3：创建 API 客户端 `frontend/src/api/client.ts`**

```typescript
import axios from "axios";

const client = axios.create({ baseURL: "/api" });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default client;
```

**Step 4：提交**

```bash
git add frontend/
git commit -m "feat: Vue 3 frontend project setup with Bun"
git push
```

---

### Task 10：登录 / 注册页面

**Files:**
- Create: `frontend/src/stores/auth.ts`
- Create: `frontend/src/pages/LoginPage.vue`
- Create: `frontend/src/pages/RegisterPage.vue`
- Create: `frontend/src/router/index.ts`

**Step 1：实现 `frontend/src/stores/auth.ts`**

```typescript
import { defineStore } from "pinia";
import client from "@/api/client";

export const useAuthStore = defineStore("auth", {
  state: () => ({ token: localStorage.getItem("token") as string | null }),
  getters: { isLoggedIn: (s) => !!s.token },
  actions: {
    async login(email: string, password: string) {
      const { data } = await client.post("/auth/login", { email, password });
      this.token = data.access_token;
      localStorage.setItem("token", data.access_token);
    },
    async register(email: string, password: string, display_name?: string) {
      const { data } = await client.post("/auth/register", { email, password, display_name });
      this.token = data.access_token;
      localStorage.setItem("token", data.access_token);
    },
    logout() {
      this.token = null;
      localStorage.removeItem("token");
    },
  },
});
```

**Step 2：实现路由 `frontend/src/router/index.ts`**

```typescript
import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("@/pages/LoginPage.vue") },
    { path: "/register", component: () => import("@/pages/RegisterPage.vue") },
    { path: "/", component: () => import("@/pages/ChatPage.vue"), meta: { requiresAuth: true } },
    { path: "/documents", component: () => import("@/pages/DocumentsPage.vue"), meta: { requiresAuth: true } },
    { path: "/settings", component: () => import("@/pages/SettingsPage.vue"), meta: { requiresAuth: true } },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.isLoggedIn) return "/login";
});

export default router;
```

**Step 3：实现 `frontend/src/pages/LoginPage.vue`**

```vue
<template>
  <div class="auth-page">
    <h1>登录 JARVIS</h1>
    <form @submit.prevent="handleLogin">
      <input v-model="email" type="email" placeholder="邮箱" required />
      <input v-model="password" type="password" placeholder="密码" required />
      <button type="submit" :disabled="loading">{{ loading ? "登录中..." : "登录" }}</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
    <p>没有账号？<router-link to="/register">注册</router-link></p>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const email = ref(""), password = ref(""), error = ref(""), loading = ref(false);

async function handleLogin() {
  loading.value = true;
  error.value = "";
  try {
    await auth.login(email.value, password.value);
    router.push("/");
  } catch {
    error.value = "邮箱或密码错误";
  } finally {
    loading.value = false;
  }
}
</script>
```

**Step 4：提交**

```bash
git add frontend/src/
git commit -m "feat: login and register pages with auth store"
git push
```

---

### Task 11：聊天界面（流式输出）

**Files:**
- Create: `frontend/src/pages/ChatPage.vue`
- Create: `frontend/src/components/MessageList.vue`
- Create: `frontend/src/components/MessageInput.vue`
- Create: `frontend/src/stores/chat.ts`

**Step 1：实现 `frontend/src/stores/chat.ts`**

```typescript
import { defineStore } from "pinia";
import client from "@/api/client";

interface Message { role: "human" | "ai"; content: string }
interface Conversation { id: string; title: string }

export const useChatStore = defineStore("chat", {
  state: () => ({
    conversations: [] as Conversation[],
    currentConvId: null as string | null,
    messages: [] as Message[],
    streaming: false,
  }),
  actions: {
    async loadConversations() {
      const { data } = await client.get("/conversations");
      this.conversations = data;
    },
    async newConversation() {
      const { data } = await client.post("/conversations", { title: "New Chat" });
      this.conversations.unshift(data);
      this.currentConvId = data.id;
      this.messages = [];
    },
    async sendMessage(content: string) {
      if (!this.currentConvId) return;
      this.messages.push({ role: "human", content });
      this.streaming = true;
      const aiMsg: Message = { role: "ai", content: "" };
      this.messages.push(aiMsg);

      const token = localStorage.getItem("token");
      const resp = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ conversation_id: this.currentConvId, content }),
      });

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value);
        for (const line of text.split("\n")) {
          if (line.startsWith("data: ")) {
            const data = JSON.parse(line.slice(6));
            aiMsg.content = data.content;
          }
        }
      }
      this.streaming = false;
    },
  },
});
```

**Step 2：实现 `frontend/src/pages/ChatPage.vue`**

```vue
<template>
  <div class="chat-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <button @click="chat.newConversation()">+ 新对话</button>
      <ul>
        <li v-for="conv in chat.conversations" :key="conv.id"
            :class="{ active: conv.id === chat.currentConvId }"
            @click="chat.currentConvId = conv.id">
          {{ conv.title }}
        </li>
      </ul>
      <div class="sidebar-footer">
        <router-link to="/documents">知识库</router-link>
        <router-link to="/settings">设置</router-link>
        <button @click="auth.logout(); router.push('/login')">退出</button>
      </div>
    </aside>

    <!-- 主区域 -->
    <main class="chat-main">
      <div class="messages" ref="messagesEl">
        <div v-for="(msg, i) in chat.messages" :key="i" :class="['message', msg.role]">
          <p>{{ msg.content }}</p>
        </div>
      </div>
      <div class="input-area">
        <!-- 语音按钮占位（后期接入） -->
        <button class="voice-btn" disabled title="语音功能即将上线">🎤</button>
        <textarea v-model="input" @keydown.enter.exact.prevent="send"
                  placeholder="输入消息，Enter 发送..." :disabled="chat.streaming" />
        <button @click="send" :disabled="chat.streaming || !input.trim()">发送</button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from "vue";
import { useRouter } from "vue-router";
import { useChatStore } from "@/stores/chat";
import { useAuthStore } from "@/stores/auth";

const chat = useChatStore();
const auth = useAuthStore();
const router = useRouter();
const input = ref("");
const messagesEl = ref<HTMLElement>();

onMounted(() => chat.loadConversations());

watch(() => chat.messages.length, async () => {
  await nextTick();
  messagesEl.value?.scrollTo(0, messagesEl.value.scrollHeight);
});

async function send() {
  if (!input.value.trim() || chat.streaming) return;
  const msg = input.value;
  input.value = "";
  if (!chat.currentConvId) await chat.newConversation();
  await chat.sendMessage(msg);
}
</script>
```

**Step 3：提交**

```bash
git add frontend/src/
git commit -m "feat: chat page with streaming SSE and sidebar"
git push
```

---

### Task 12：文件上传页 + 设置页

**Files:**
- Create: `frontend/src/pages/DocumentsPage.vue`
- Create: `frontend/src/pages/SettingsPage.vue`

**Step 1：实现 `frontend/src/pages/DocumentsPage.vue`**

```vue
<template>
  <div class="documents-page">
    <h2>知识库</h2>
    <input type="file" accept=".pdf,.txt,.md,.docx" @change="upload" :disabled="uploading" />
    <p v-if="uploading">上传中...</p>
    <p v-if="result">{{ result }}</p>
    <router-link to="/">← 返回聊天</router-link>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import client from "@/api/client";

const uploading = ref(false), result = ref("");

async function upload(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (!file) return;
  if (file.size > 50 * 1024 * 1024) { result.value = "文件不能超过 50MB"; return; }
  uploading.value = true;
  const form = new FormData();
  form.append("file", file);
  try {
    const { data } = await client.post("/documents", form);
    result.value = `上传成功，共切分 ${data.chunk_count} 个片段`;
  } catch {
    result.value = "上传失败，请检查文件格式";
  } finally {
    uploading.value = false;
  }
}
</script>
```

**Step 2：实现 `frontend/src/pages/SettingsPage.vue`**

```vue
<template>
  <div class="settings-page">
    <h2>设置</h2>
    <label>模型提供商
      <select v-model="provider">
        <option value="deepseek">DeepSeek</option>
        <option value="openai">OpenAI</option>
        <option value="anthropic">Anthropic</option>
      </select>
    </label>
    <label>模型名称 <input v-model="modelName" /></label>
    <label>API Key <input v-model="apiKey" type="password" /></label>
    <button @click="save">保存</button>
    <p v-if="saved">已保存</p>
    <router-link to="/">← 返回聊天</router-link>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import client from "@/api/client";

const provider = ref("deepseek"), modelName = ref("deepseek-chat"), apiKey = ref(""), saved = ref(false);

async function save() {
  await client.put("/settings", {
    model_provider: provider.value,
    model_name: modelName.value,
    api_keys: { [provider.value]: apiKey.value },
  });
  saved.value = true;
  setTimeout(() => (saved.value = false), 2000);
}
</script>
```

**Step 3：添加 settings API 端点到后端 `backend/app/api/settings.py`**

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.models import User, UserSettings
from app.db.session import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    model_provider: str
    model_name: str
    api_keys: dict[str, str]


@router.put("")
async def update_settings(
    body: SettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await db.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    if not s:
        s = UserSettings(user_id=user.id)
        db.add(s)
    s.model_provider = body.model_provider
    s.model_name = body.model_name
    s.api_keys = body.api_keys
    await db.commit()
    return {"status": "ok"}
```

**Step 4：提交**

```bash
git add frontend/src/ backend/app/api/settings.py
git commit -m "feat: documents upload page and settings page"
git push
```

---

## Phase 8：集成验证

### Task 13：端到端冒烟测试

**Files:**
- Test: `backend/tests/test_e2e.py`

**Step 1：写端到端测试**

```python
# backend/tests/test_e2e.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_full_flow(client):
    # 1. 注册
    r = await client.post("/api/auth/register", json={"email": "e2e@test.com", "password": "pass123"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. 创建对话
    r = await client.post("/api/conversations", json={"title": "E2E Test"}, headers=headers)
    assert r.status_code == 201
    conv_id = r.json()["id"]

    # 3. 列出对话
    r = await client.get("/api/conversations", headers=headers)
    assert r.status_code == 200
    assert any(c["id"] == conv_id for c in r.json())

    # 4. 健康检查
    r = await client.get("/health")
    assert r.json() == {"status": "ok"}
```

**Step 2：运行确认通过**

```bash
uv run pytest tests/test_e2e.py -v
# Expected: PASS
```

**Step 3：启动完整 Docker 环境验证**

```bash
cp .env.example .env
# 编辑 .env 填入真实 API Key
docker compose up --build
# 访问 http://localhost:3000 验证前端
# 访问 http://localhost:8000/docs 验证 API
```

**Step 4：最终提交**

```bash
git add backend/tests/test_e2e.py
git commit -m "test: end-to-end smoke tests"
git push
```

---

## 实现顺序总览

| Phase | Task | 预计复杂度 |
|-------|------|-----------|
| 1 | Task 1: Docker Compose + 目录结构 | 低 |
| 1 | Task 2: 配置 + DB 连接 | 低 |
| 2 | Task 3: SQLAlchemy 模型 + Alembic | 中 |
| 3 | Task 4: 注册/登录 JWT | 中 |
| 3 | Task 5: 对话 CRUD | 低 |
| 4 | Task 6: LangGraph Agent + 流式输出 | 高 |
| 5 | Task 7: 4 个内置工具 | 中 |
| 6 | Task 8: RAG 文档上传 + 向量化 | 高 |
| 7 | Task 9: Vue 前端初始化 | 低 |
| 7 | Task 10: 登录/注册页 | 低 |
| 7 | Task 11: 聊天界面 | 中 |
| 7 | Task 12: 文档页 + 设置页 | 低 |
| 8 | Task 13: 端到端测试 | 低 |
