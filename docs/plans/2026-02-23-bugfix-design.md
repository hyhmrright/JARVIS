# Jarvis Bug Fix Design — 2026-02-23

## 背景

代码审查发现 17 个问题：3 个严重（Critical）、7 个重要（Important）、7 个建议（Suggestion）。本文档描述每个问题的修复方案设计。

---

## Critical 修复

### C1：对话历史损坏（`app/api/chat.py:56`）

**现状**：只将 `human` 消息转为 `HumanMessage`，AI 消息被丢弃。
**方案**：从数据库加载全部消息，按 `role` 映射到 `HumanMessage` / `AIMessage`。

### C2：StreamingResponse 内 DB session 关闭（`app/api/chat.py:71`）

**现状**：`generate()` 协程捕获了路由依赖提供的 `AsyncSession`，但路由函数返回后依赖已被销毁。
**方案**：在 `generate()` 内部通过 `AsyncSessionLocal()` 创建独立 session，完全不依赖外部 session。

### C3：代码执行无沙箱 + timeout 不 kill（`app/tools/code_exec_tool.py`）

**现状**：`asyncio.wait_for` 超时后子进程仍在运行；docstring 声称是"沙箱"但毫无限制。
**方案**：
- timeout 时调用 `proc.kill()` 再 `await proc.wait()`
- 在子进程参数加 `-I`（isolated mode：禁用 site-packages、用户目录、PYTHONPATH）
- 更新 docstring，说明这是资源限制而非完整隔离沙箱

---

## Important 修复

### I4：MinIO 同步调用阻塞事件循环（`app/api/documents.py`）

**方案**：用 `asyncio.to_thread()` 包装 `bucket_exists`、`make_bucket`、`put_object`。

### I5：MinIO object key 路径注入（`app/api/documents.py:58`）

**方案**：使用 `Path(file.filename).name` 取纯文件名，再加 UUID4 前缀，格式为 `{user_id}/{uuid4}_{safe_filename}`。

### I6：`enabled_tools` 存储但从不生效（`app/agent/graph.py`）

**方案**：`create_graph()` 增加 `enabled_tools: list[str]` 参数，用工具名称过滤 `TOOLS` 列表；在 `chat.py` 中读取用户设置并传入。工具名称映射：`search` → `web_search`，`code_exec` → `execute_code`，`datetime` → `get_datetime`。

### I7：API Key 明文存储（`app/db/models.py`）

**方案**：
- `config.py` 新增 `encryption_key: str`（32 字节 base64，有默认值用于开发）
- `security.py` 新增 `encrypt_api_keys()` / `decrypt_api_keys()` 函数，使用 `cryptography.fernet`
- `settings.py` API（读/写 UserSettings 的接口）在入库前加密、返回前解密
- 现有明文数据通过 migration 脚本一次性加密（Alembic migration）

### I8：前端 streaming 异常时 UI 永久禁用（`frontend/src/stores/chat.ts`）

**方案**：
- `sendMessage` 用 `try/finally` 包裹，`finally` 块设置 `this.streaming = false`
- 在 `resp.body` 为 null 时提前 throw
- 捕获 JSON parse 错误，跳过无法解析的行

### I9：测试依赖真实 PG，无运行间隔离（`backend/tests/`）

**方案**：
- 新建 `backend/tests/conftest.py`，覆盖 `settings.database_url` 为 SQLite in-memory
- 用 `pytest fixture`（scope=`function`）在每个测试前创建所有表、测试后删除
- 覆盖 FastAPI 的 `get_db` 依赖，注入测试 session

### I10：`python-jose` 已停维护（`backend/pyproject.toml`）

**方案**：
- `pyproject.toml` 中将 `python-jose[cryptography]` 替换为 `PyJWT[crypto]`
- `security.py` 中 `from jose import jwt` → `import jwt`，适配 PyJWT API（`jwt.encode` 返回 `str`，`jwt.decode` 接口相同）

---

## Suggestion 修复

### S11：Dockerfile `--reload` 无注释

**方案**：加注释说明仅用于开发环境，不修改功能。

### S12：frontend Dockerfile 锁文件名错误

**方案**：`bun.lockb*` → `bun.lock*`。

### S13：CORS origins 硬编码

**方案**：`config.py` 新增 `cors_origins: list[str] = ["http://localhost:3000"]`；`main.py` 使用 `settings.cors_origins`。

### S14：`create_graph` 返回 `Any`

**方案**：改返回类型为 `CompiledStateGraph`。

### S15：认证接口无频率限制

**方案**：添加 `slowapi` 依赖；在 `main.py` 注册 `SlowAPI` 限速器；登录 5次/分钟，注册 3次/分钟，超限返回 429。

### S16：测试断言改动未注释

**方案**：在 `test_chunker.py` 加注释说明用词数而非字符数更准确。

### S17：search_tool docstring 夸大能力

**方案**：更新 docstring 如实描述 DuckDuckGo Instant Answer API 的局限性。

---

## 文件修改清单

| 文件 | 影响的 issue |
|------|-------------|
| `backend/app/api/chat.py` | C1, C2, I6 |
| `backend/app/tools/code_exec_tool.py` | C3 |
| `backend/app/api/documents.py` | I4, I5 |
| `backend/app/agent/graph.py` | I6, S14 |
| `backend/app/core/config.py` | I7, S13, S15 |
| `backend/app/core/security.py` | I7, I10 |
| `backend/app/api/settings.py` | I7 |
| `backend/app/main.py` | S13, S15 |
| `frontend/src/stores/chat.ts` | I8 |
| `backend/tests/conftest.py` | I9（新建） |
| `backend/pyproject.toml` | I10, S15 |
| `backend/Dockerfile` | S11 |
| `frontend/Dockerfile` | S12 |
| `backend/tests/rag/test_chunker.py` | S16 |
| `backend/app/tools/search_tool.py` | S17 |
