# Jarvis Bug Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复代码审查发现的 17 个问题（3 Critical、7 Important、7 Suggestion）。

**Architecture:** 后端 FastAPI + LangGraph + PostgreSQL + MinIO；前端 Vue 3 + Pinia。修复涵盖安全加固、并发正确性、类型改进和测试隔离。

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, LangGraph, PyJWT (替换 python-jose), cryptography (新增), slowapi (新增), Bun + Vue 3 + TypeScript。

---

## Task 1: 替换 python-jose 为 PyJWT（I10）

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/security.py`

**Step 1: 更新依赖**

编辑 `backend/pyproject.toml`，将：
```toml
"python-jose[cryptography]>=3.3.0",
```
替换为：
```toml
"PyJWT[crypto]>=2.10.0",
"cryptography>=44.0.0",
```

**Step 2: 在 backend 目录安装新依赖**

```bash
cd /Users/hyh/code/agents/backend && uv sync
```
Expected: 安装 PyJWT，移除 python-jose

**Step 3: 更新 security.py**

将 `backend/app/core/security.py` 全部内容替换为：
```python
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


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
```

**Step 4: 验证导入正常**

```bash
cd /Users/hyh/code/agents/backend && uv run python -c "from app.core.security import create_access_token, decode_access_token; print('OK')"
```
Expected: `OK`

**Step 5: Commit**

```bash
cd /Users/hyh/code/agents/backend && git add pyproject.toml uv.lock app/core/security.py && git commit -m "fix: replace unmaintained python-jose with PyJWT"
```

---

## Task 2: 更新 config.py，新增加密密钥和 CORS 配置（I7 prep, S13）

**Files:**
- Modify: `backend/app/core/config.py`

**Step 1: 更新 config.py**

将 `backend/app/core/config.py` 替换为：
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
    # 32-byte URL-safe base64 key；生产环境必须通过环境变量覆盖
    # 生成方式：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str = "V2hhdCBhIG5pY2UgZGF5IHRvIGZpeCBidWdzISEh"
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
```

**Step 2: 验证**

```bash
cd /Users/hyh/code/agents/backend && uv run python -c "from app.core.config import settings; print(settings.cors_origins)"
```
Expected: `['http://localhost:3000']`

**Step 3: Commit**

```bash
cd /Users/hyh/code/agents/backend && git add app/core/config.py && git commit -m "feat: add encryption_key and cors_origins to settings"
```

---

## Task 3: 实现 API Key 加密存储（I7）

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/api/settings.py`

**Step 1: 在 security.py 末尾添加加密函数**

在 `decode_access_token` 函数之后追加：
```python

def _get_fernet():
    from cryptography.fernet import Fernet
    from app.core.config import settings

    key = settings.encryption_key.encode()
    # Fernet 要求 32 字节 URL-safe base64 key；如果原始字节不足则用 base64 补全
    import base64
    try:
        Fernet(key)
        return Fernet(key)
    except Exception:
        # 回退：对 key 做 base64 编码使其符合 Fernet 格式
        padded = base64.urlsafe_b64encode(key[:32].ljust(32, b"\x00"))
        return Fernet(padded)


def encrypt_api_keys(api_keys: dict) -> dict:
    """将 api_keys 字典中的所有值加密后返回新字典。"""
    import json
    f = _get_fernet()
    encrypted = f.encrypt(json.dumps(api_keys).encode()).decode()
    return {"__encrypted__": encrypted}


def decrypt_api_keys(stored: dict) -> dict:
    """解密 api_keys 字典。若不是加密格式则原样返回（兼容旧数据）。"""
    import json
    if "__encrypted__" not in stored:
        return stored
    f = _get_fernet()
    decrypted = f.decrypt(stored["__encrypted__"].encode())
    return json.loads(decrypted)
```

**Step 2: 更新 settings.py，在存入时加密、返回时解密**

将 `backend/app/api/settings.py` 全部替换为：
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import decrypt_api_keys, encrypt_api_keys
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
    s.api_keys = encrypt_api_keys(dict(body.api_keys))
    await db.commit()
    return {"status": "ok"}


@router.get("")
async def get_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    s = await db.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    if not s:
        return {"model_provider": "deepseek", "model_name": "deepseek-chat", "api_keys": {}}
    return {
        "model_provider": s.model_provider,
        "model_name": s.model_name,
        "api_keys": decrypt_api_keys(s.api_keys),
    }
```

**Step 3: 验证加密函数**

```bash
cd /Users/hyh/code/agents/backend && uv run python -c "
from app.core.security import encrypt_api_keys, decrypt_api_keys
orig = {'openai': 'sk-test123'}
enc = encrypt_api_keys(orig)
assert '__encrypted__' in enc
dec = decrypt_api_keys(enc)
assert dec == orig
print('Encryption OK')
"
```
Expected: `Encryption OK`

**Step 4: chat.py 中读取 api_keys 时也需要解密，更新 chat.py 相关行**

在 `backend/app/api/chat.py` 中找到：
```python
    api_keys = user_settings.api_keys if user_settings else {}
```
替换为：
```python
    from app.core.security import decrypt_api_keys
    raw_keys = user_settings.api_keys if user_settings else {}
    api_keys = decrypt_api_keys(raw_keys)
```

**Step 5: Commit**

```bash
cd /Users/hyh/code/agents/backend && git add app/core/security.py app/api/settings.py app/api/chat.py && git commit -m "feat: encrypt API keys at rest using Fernet"
```

---

## Task 4: 修复多轮对话历史 + StreamingResponse DB session（C1、C2）

**Files:**
- Modify: `backend/app/api/chat.py`

**Step 1: 将 chat.py 全部替换**

```python
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import create_graph
from app.agent.state import AgentState
from app.api.deps import get_current_user
from app.core.security import decrypt_api_keys
from app.db.models import Conversation, Message, User, UserSettings
from app.db.session import AsyncSessionLocal, get_db

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
    conv = await db.scalar(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404)

    user_settings = await db.scalar(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    provider = user_settings.model_provider if user_settings else "deepseek"
    model_name = user_settings.model_name if user_settings else "deepseek-chat"
    raw_keys = user_settings.api_keys if user_settings else {}
    api_key = decrypt_api_keys(raw_keys).get(provider, "")
    enabled_tools = user_settings.enabled_tools if user_settings else None

    db.add(Message(conversation_id=conv.id, role="human", content=body.content))
    await db.commit()

    # 加载完整对话历史（human + ai），构造 LangChain 消息列表
    history_rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    lc_messages = []
    for msg in history_rows.all():
        if msg.role == "human":
            lc_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "ai":
            lc_messages.append(AIMessage(content=msg.content))

    conv_id = conv.id

    async def generate():
        # generate() 使用独立 session，避免依赖外部已关闭的 session
        graph = create_graph(
            provider=provider,
            model=model_name,
            api_key=api_key,
            enabled_tools=enabled_tools,
        )
        full_content = ""
        async for chunk in graph.astream(AgentState(messages=lc_messages)):
            if "llm" in chunk:
                ai_msg = chunk["llm"]["messages"][-1]
                full_content = ai_msg.content
                data = json.dumps({"content": full_content})
                yield "data: " + data + "\n\n"

        async with AsyncSessionLocal() as session:
            async with session.begin():
                session.add(
                    Message(
                        conversation_id=conv_id,
                        role="ai",
                        content=full_content,
                        model_provider=provider,
                        model_name=model_name,
                    )
                )

    return StreamingResponse(generate(), media_type="text/event-stream")
```

**Step 2: 验证 session.py 导出了 AsyncSessionLocal**

查看 `backend/app/db/session.py`，确认有 `AsyncSessionLocal`，若没有则在该文件中它已被定义（`async_sessionmaker` 的结果）。如果变量名不同，确保 import 正确。

**Step 3: 导入验证**

```bash
cd /Users/hyh/code/agents/backend && uv run python -c "from app.api.chat import router; print('chat router OK')"
```
Expected: `chat router OK`

**Step 4: Commit**

```bash
cd /Users/hyh/code/agents/backend && git add app/api/chat.py && git commit -m "fix: restore full conversation history and fix streaming DB session leak"
```

---

## Task 5: 修复 graph.py — enabled_tools 生效 + 返回类型（I6、S14）

**Files:**
- Modify: `backend/app/agent/graph.py`

**Step 1: 替换 graph.py**

```python
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage

from app.agent.llm import get_llm
from app.agent.state import AgentState
from app.tools.code_exec_tool import execute_code
from app.tools.datetime_tool import get_datetime
from app.tools.search_tool import web_search

# 工具名称 → 工具对象的映射（与 UserSettings.enabled_tools 的值对应）
_TOOL_MAP = {
    "search": web_search,
    "code_exec": execute_code,
    "datetime": get_datetime,
}

_DEFAULT_TOOLS = list(_TOOL_MAP.values())


def create_graph(
    provider: str,
    model: str,
    api_key: str,
    enabled_tools: list[str] | None = None,
) -> CompiledStateGraph:
    tools = (
        [_TOOL_MAP[name] for name in enabled_tools if name in _TOOL_MAP]
        if enabled_tools is not None
        else _DEFAULT_TOOLS
    )

    llm = get_llm(provider, model, api_key)
    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    async def call_llm(state: AgentState) -> dict[str, list[BaseMessage]]:
        response = await llm_with_tools.ainvoke(state.messages)
        return {"messages": [response]}

    def should_use_tool(state: AgentState) -> str:
        last = state.messages[-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph: StateGraph[AgentState] = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", should_use_tool)
    graph.add_edge("tools", "llm")
    return graph.compile()
```

**Step 2: 验证**

```bash
cd /Users/hyh/code/agents/backend && uv run python -c "from app.agent.graph import create_graph; print('graph OK')"
```
Expected: `graph OK`

**Step 3: Commit**

```bash
cd /Users/hyh/code/agents/backend && git add app/agent/graph.py && git commit -m "fix: wire enabled_tools into graph, fix return type Any -> CompiledStateGraph"
```

---

## Task 6: 修复代码执行工具 — kill 子进程 + 隔离模式（C3）

**Files:**
- Modify: `backend/app/tools/code_exec_tool.py`

**Step 1: 替换 code_exec_tool.py**

```python
import asyncio

from langchain_core.tools import tool


@tool
async def execute_code(code: str) -> str:
    """Execute Python code and return the output.

    NOTE: This runs code in an isolated Python interpreter (-I flag: no site-packages,
    no user site, no PYTHONPATH). It is NOT a full OS-level sandbox — do not use in
    untrusted multi-tenant environments without additional container isolation.
    """
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3",
            "-I",  # isolated mode: disables site-packages, user site, PYTHONPATH
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        if stderr:
            return f"Error: {stderr.decode()}"
        return stdout.decode() or "(no output)"
    except TimeoutError:
        if proc is not None:
            proc.kill()
            await proc.wait()
        return "Timeout: code execution exceeded 30 seconds"
```

**Step 2: Commit**

```bash
cd /Users/hyh/code/agents/backend && git add app/tools/code_exec_tool.py && git commit -m "fix: kill subprocess on timeout, add Python -I isolated mode"
```

---

## Task 7: 修复 MinIO 同步阻塞 + 路径注入（I4、I5）

**Files:**
- Modify: `backend/app/api/documents.py`

**Step 1: 替换 documents.py**

```python
import asyncio
import io
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from minio import Minio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import decrypt_api_keys
from app.db.models import Document, User, UserSettings
from app.db.session import get_db
from app.rag.indexer import index_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_TYPES = {"pdf", "txt", "md", "docx"}
MAX_SIZE = 50 * 1024 * 1024


def extract_text(content: bytes, file_type: str) -> str:
    if file_type in ("txt", "md"):
        return content.decode("utf-8", errors="ignore")
    if file_type == "pdf":
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    if file_type == "docx":
        import docx

        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    return ""


def _get_minio_client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )


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

    # 用 Path().name 防止路径注入，再加 UUID 前缀避免同名文件覆盖
    safe_name = Path(file.filename or "upload").name
    object_key = f"{user.id}/{uuid.uuid4()}_{safe_name}"

    minio_client = _get_minio_client()

    # 用 asyncio.to_thread 包装同步 MinIO 调用，避免阻塞事件循环
    bucket_exists = await asyncio.to_thread(
        minio_client.bucket_exists, settings.minio_bucket
    )
    if not bucket_exists:
        await asyncio.to_thread(minio_client.make_bucket, settings.minio_bucket)
    await asyncio.to_thread(
        minio_client.put_object,
        settings.minio_bucket,
        object_key,
        io.BytesIO(content),
        len(content),
    )

    user_settings = await db.scalar(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    raw_keys = (user_settings.api_keys or {}) if user_settings else {}
    api_key = decrypt_api_keys(raw_keys).get(
        user_settings.model_provider if user_settings else "deepseek", ""
    )

    text = extract_text(content, ext)
    doc = Document(
        user_id=user.id,
        filename=safe_name,
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

**Step 2: Commit**

```bash
cd /Users/hyh/code/agents/backend && git add app/api/documents.py && git commit -m "fix: wrap MinIO calls in asyncio.to_thread, sanitize filename with UUID prefix"
```

---

## Task 8: 添加 slowapi 频率限制（S15）

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/auth.py`

**Step 1: 添加 slowapi 依赖**

编辑 `backend/pyproject.toml`，在 `dependencies` 列表中添加：
```toml
"slowapi>=0.1.9",
```

```bash
cd /Users/hyh/code/agents/backend && uv sync
```

**Step 2: 更新 main.py**

将 `backend/app/main.py` 替换为：
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.settings import router as settings_router
from app.core.config import settings

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Jarvis API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(settings_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 3: 更新 auth.py，添加限速装饰器**

将 `backend/app/api/auth.py` 替换为：
```python
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User, UserSettings
from app.db.session import get_db
from app.main import limiter

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
@limiter.limit("3/minute")
async def register(
    request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)
):
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
):
    user = await db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(str(user.id)))
```

**Step 4: 验证启动**

```bash
cd /Users/hyh/code/agents/backend && uv run python -c "from app.main import app; print('app OK')"
```
Expected: `app OK`

**Step 5: Commit**

```bash
cd /Users/hyh/code/agents/backend && git add pyproject.toml uv.lock app/main.py app/api/auth.py && git commit -m "feat: add slowapi rate limiting (login 5/min, register 3/min), CORS from config"
```

---

## Task 9: 修复前端 streaming 异常不重置标志（I8）

**Files:**
- Modify: `frontend/src/stores/chat.ts`

**Step 1: 替换 sendMessage action**

将 `frontend/src/stores/chat.ts` 中的 `sendMessage` action 替换为：
```typescript
async sendMessage(content: string) {
  if (!this.currentConvId) return;
  this.messages.push({ role: "human", content });
  this.streaming = true;
  const aiMsg: Message = { role: "ai", content: "" };
  this.messages.push(aiMsg);

  try {
    const token = localStorage.getItem("token");
    const resp = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ conversation_id: this.currentConvId, content }),
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    if (!resp.body) throw new Error("No response body");

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value);
      for (const line of text.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            aiMsg.content = data.content;
          } catch {
            // 跳过无法解析的 SSE 行
          }
        }
      }
    }
  } finally {
    this.streaming = false;
  }
},
```

**Step 2: Commit**

```bash
cd /Users/hyh/code/agents && git add frontend/src/stores/chat.ts && git commit -m "fix: reset streaming flag in finally block, add null check on resp.body"
```

---

## Task 10: 修复测试隔离 — 添加 conftest.py（I9）

**Files:**
- Create: `backend/tests/conftest.py`

**Step 1: 创建 conftest.py**

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# 测试数据库：使用单独的 test 数据库，避免污染开发数据
TEST_DATABASE_URL = "postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis_test"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def test_engine():
    """每次测试 session 创建所有表，结束后删除。"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """每个测试使用独立事务，测试结束后回滚，保证测试间互不影响。"""
    async with test_engine.begin() as conn:
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


@pytest.fixture
async def client(db_session):
    """提供已配置好的测试 HTTP 客户端，注入测试 DB session。"""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client(client):
    """已登录的测试客户端（自动注册并获取 token）。"""
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

**Step 2: 删除各测试文件中重复的 fixture 定义**

- `backend/tests/api/test_auth.py`：删除文件内的 `client` fixture（第 6-11 行）
- `backend/tests/api/test_conversations.py`：删除文件内的 `auth_client` fixture（第 6-17 行）

**Step 3: 确认测试文件使用 conftest 的 fixture**

各测试文件中的测试函数签名不需要改变（`client`、`auth_client` 名称相同）。

**Step 4: Commit**

```bash
cd /Users/hyh/code/agents/backend && git add tests/conftest.py tests/api/test_auth.py tests/api/test_conversations.py && git commit -m "fix: add conftest.py with isolated test DB, remove duplicate fixtures"
```

---

## Task 11: 剩余小修复（S11、S12、S16、S17）

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `frontend/Dockerfile`
- Modify: `backend/tests/rag/test_chunker.py`
- Modify: `backend/app/tools/search_tool.py`

**Step 1: 修复 backend Dockerfile — 添加注释说明 --reload**

在 `backend/Dockerfile` 的 CMD 行前添加注释：
```dockerfile
# NOTE: --reload enables hot-reload for development. Remove for production images.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

**Step 2: 修复 frontend Dockerfile — 锁文件名**

将 `frontend/Dockerfile` 中：
```dockerfile
COPY package.json bun.lockb* ./
```
改为：
```dockerfile
COPY package.json bun.lock* ./
```

**Step 3: 给 test_chunker.py 添加注释**

在 `backend/tests/rag/test_chunker.py` 的断言行添加注释：
```python
    # 用词数（word count）而非字符数断言，与 chunk_text 的 chunk_size 语义一致
    assert all(len(c.split()) <= 200 for c in chunks)
```

**Step 4: 更新 search_tool.py docstring**

将 `backend/app/tools/search_tool.py` 中的 docstring 替换为：
```python
    """Search using DuckDuckGo Instant Answer API.

    Note: This API returns Wikipedia-style abstracts and related topics only.
    It does NOT perform general web search. Most queries will return empty results.
    query is the search term.
    """
```

**Step 5: Commit**

```bash
cd /Users/hyh/code/agents && git add backend/Dockerfile frontend/Dockerfile backend/tests/rag/test_chunker.py backend/app/tools/search_tool.py && git commit -m "fix: Dockerfile comments, bun.lock filename, test comment, search_tool docstring"
```

---

## 完成后验证

```bash
# 后端 lint
cd /Users/hyh/code/agents/backend && uv run ruff check && uv run ruff format --check

# 后端类型检查
cd /Users/hyh/code/agents/backend && uv run pyright

# 启动确认（不需要真实服务）
cd /Users/hyh/code/agents/backend && uv run python -c "
from app.main import app
from app.agent.graph import create_graph
from app.core.security import encrypt_api_keys, decrypt_api_keys
from app.api.chat import router
print('All imports OK')
"
```
