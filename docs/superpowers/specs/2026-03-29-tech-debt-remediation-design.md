# JARVIS 技术债务修复设计

**日期：** 2026-03-29
**来源：** Brooks-Lint Tech Debt Assessment（Mode 3）
**健康分：** 42/100 → 目标 85/100
**范围：** `backend/app/` 全部后端代码

---

## 背景

Brooks-Lint 审计发现 10 个问题，分布在 5 个子项目中，按优先级顺序执行：

| 子项目 | 解决问题 | 风险 |
|--------|---------|------|
| P1: Core Agent 重构 | Critical ×2，Warning ×2 | 高 |
| P2: 依赖结构修复 | Warning ×1，Suggestion ×1 | 低 |
| P3: 测试覆盖补全 | Warning ×1 | 低 |
| P4: API 标准化 | Suggestion ×2 | 极低 |
| P5: 领域模型增强 | Warning ×1 | 极高 |

---

## P1：Core Agent 重构

### 目标

- `chat_stream()` 从 472 行 → ≤50 行
- `create_graph()` 从 17 个参数 → 2 个
- 三处重复的 agent 执行逻辑统一到一个服务
- `chat_regenerate()` 复用底层实现，消除 280 行影子副本

### 新增文件：`app/services/agent_execution.py`

```python
@dataclass
class AgentConfig:
    """统一的 agent 运行配置，替换 create_graph() 的 17 个散参数。"""
    llm_config: ResolvedLLMConfig
    enabled_tools: list[str]
    persona_prompt: str | None = None
    workflow_dsl: dict | None = None

class AgentExecutionService:
    """统一 agent 执行入口，支持流式和阻塞两种模式。"""

    async def run_streaming(
        self,
        messages: list[BaseMessage],
        config: AgentConfig,
        db: AsyncSession,
    ) -> AsyncIterator[AgentEvent]:
        """
        用于 SSE 路径（chat_stream, chat_regenerate）。
        AgentEvent 是内部 TypedDict，表示一次流式事件，字段包括：
          type: "text" | "tool_call" | "tool_result" | "done"
          content: str
          metadata: dict（token 统计、tool 名称等）
        """
        ...

    async def run_blocking(
        self,
        messages: list[BaseMessage],
        config: AgentConfig,
        db: AsyncSession,
    ) -> str:
        """用于后台路径（gateway, cron/webhook agent runner）。"""
        ...
```

### 新增文件：`app/services/chat_context.py`

```python
@dataclass
class ChatContext:
    messages: list[BaseMessage]
    config: AgentConfig
    conversation_id: UUID
    agent_session_id: UUID | None

async def build_chat_context(
    request: ChatRequest,
    user: User,
    db: AsyncSession,
) -> ChatContext:
    """
    构建 agent 执行所需的完整上下文：
    1. 加载消息历史（tree walk）
    2. 注入 RAG 上下文
    3. 解析 LLM 配置 + persona 覆盖
    4. 构造 AgentConfig
    """
    ...
```

### 重构后的调用结构

```
api/chat/routes.py::chat_stream()       [≤50 行]
  → build_chat_context()
  → AgentExecutionService.run_streaming()
  → StreamingResponse(SSE)

api/chat/routes.py::chat_regenerate()   [≤30 行]
  → 软删除旧消息
  → build_chat_context()
  → AgentExecutionService.run_streaming()
  → StreamingResponse(SSE)

gateway/router.py::_run_agent()         [≤30 行]
  → build_gateway_context()   # 新增辅助函数（同文件），从 channel message 构建 messages + AgentConfig
  → AgentExecutionService.run_blocking()

gateway/agent_runner.py::run_agent_for_user()  [≤30 行]
  → build_runner_context()    # 新增辅助函数（同文件），从 trigger context 构建 messages + AgentConfig
  → AgentExecutionService.run_blocking()
```

### agent/graph.py 参数简化

```python
# 之前（17 个参数）
async def create_graph(
    model_name, api_key, provider, system_prompt,
    enable_shell, enable_browser, enable_code_exec, enable_rag,
    enable_search, enable_file, enable_cron, enable_plugin,
    enable_subagent, enable_mcp, mcp_servers_json,
    tools_override, workflow_dsl
) -> CompiledGraph:

# 之后（2 个参数）
async def create_graph(
    messages: list[BaseMessage],
    config: AgentConfig,
) -> CompiledGraph:
```

### 测试策略

- 现有 `tests/api/test_chat.py` 的 mock 目标从内部实现函数迁移到 `AgentExecutionService.run_streaming`
- 新增 `tests/services/test_agent_execution.py`，测试流式和阻塞两种模式
- 重构前跑全套测试建立基线；重构后所有业务行为保持一致

---

## P2：依赖结构修复

### 2a：修复循环依赖

**问题：** `agent/graph.py` ↔ `tools/subagent_tool.py` 循环依赖，当前通过函数体内延迟导入规避。

**新增文件：`app/agent/interfaces.py`**

```python
from typing import Protocol

class AgentGraphFactory(Protocol):
    """subagent_tool 依赖此 Protocol，不依赖 graph.py 具体实现。"""
    async def create(
        self,
        messages: list[BaseMessage],
        config: AgentConfig,
    ) -> CompiledGraph: ...
```

**变更：**
- `tools/subagent_tool.py`：import `AgentGraphFactory` Protocol，不再 import `agent/graph.py`
- `main.py`：启动时将 `graph.create_graph` 实现注入 subagent_tool
- 删除 `agent/graph.py` 中的函数体延迟 import

### 2b：修复工具层直接持有 DB 会话

**问题：** `tools/cron_tool.py` 和 `tools/user_memory_tool.py` 直接 import `AsyncSessionLocal`，跨越了层次边界，导致无法单元测试。

**新增文件：`app/services/repositories.py`**

```python
class MemoryRepository:
    def __init__(self, db: AsyncSession): ...
    async def get_memories(self, user_id: UUID) -> list[UserMemory]: ...
    async def save_memory(self, user_id: UUID, content: str) -> UserMemory: ...
    async def delete_memory(self, memory_id: UUID) -> None: ...

class CronRepository:
    def __init__(self, db: AsyncSession): ...
    async def get_job(self, job_id: UUID) -> CronJob | None: ...
    async def list_jobs(self, user_id: UUID) -> list[CronJob]: ...
```

**变更：**
- `tools/user_memory_tool.py`：接受 `MemoryRepository` 注入，删除直接 `AsyncSessionLocal` import
- `tools/cron_tool.py`：接受 `CronRepository` 注入
- 调用方（`agent/graph.py` 中的工具初始化）负责创建 repository 实例并注入

---

## P3：测试覆盖补全

新增 13 个测试文件，按风险优先级排序：

### 高风险（权限 / 多租户）

**`tests/api/test_workspaces.py`**
- 测试用例：工作区成员不能访问其他工作区的资源、邀请链接过期、角色权限边界

**`tests/api/test_plugins.py`**
- 测试用例：MCP/Python/Node 三种插件类型安装、卸载、配置读写、类型判断分支

### 中风险（业务逻辑）

**`tests/api/test_cron.py`（补全）**
- 补充：trigger 评估逻辑、Redis 分布式锁、死信处理

**`tests/api/test_public.py`**
- 测试用例：公开分享链接鉴权、过期分享、无权访问分支

**`tests/api/test_gateway.py`**
- 测试用例：channel 路由分发、未知 channel 处理

### Agent 层

**`tests/agent/test_persona.py`** — persona prompt 组装、覆盖优先级

**`tests/agent/test_workflow_schema.py`** — DSL 验证边界条件（循环检测、缺失节点等）

**`tests/agent/test_state.py`** — state 初始化和字段默认值

### 工具层（5 个）

**`tests/tools/test_code_exec_tool.py`** — 沙箱限制、超时
**`tests/tools/test_user_memory_tool.py`** — 使用 MemoryRepository mock（P2b 之后）
**`tests/tools/test_datetime_tool.py`** — 时区处理
**`tests/tools/test_memory_tool.py`** — 记忆读写
**`tests/tools/test_image_gen_tool.py`** — API 调用失败处理

### 通用约定

- 所有新测试 mock 在服务/repository 边界，不 mock 数据库驱动
- 遵循现有 `conftest.py` 的 autouse fixture 模式（`_suppress_auth_audit_logging` 等）
- 异步测试使用 `@pytest.mark.anyio`

---

## P4：API 标准化

### 4a：统一分页参数

**`app/api/deps.py` 新增：**

```python
class PaginationParams:
    """统一分页参数，替换 12+ 处散乱的 limit/skip 定义。"""
    def __init__(
        self,
        skip: int = Query(0, ge=0, description="跳过的记录数"),
        limit: int = Query(50, ge=1, le=200, description="返回的最大记录数"),
    ):
        self.skip = skip
        self.limit = limit
```

各 API 端点将 `limit: int = Query(...)` 替换为 `Annotated[PaginationParams, Depends()]`，端点如需特殊上限可在路由层覆盖。

### 4b：统一非 SSE 的数据库会话创建

**`app/db/session.py` 新增：**

```python
@asynccontextmanager
async def isolated_session() -> AsyncIterator[AsyncSession]:
    """
    在非 SSE 上下文（worker、scheduler、background task）中
    替代直接使用 AsyncSessionLocal()。
    提供统一的错误处理和连接生命周期管理。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**处理策略：**
- SSE 流中的 `AsyncSessionLocal()` 直接调用：保留，添加 `# SSE context: cannot use Depends(get_db)` 注释说明合理性
- 非流式上下文的直接调用（`api/deps.py:108`、`tools/` 等）：替换为 `isolated_session()`

---

## P5：领域模型增强（消除贫血模型）

### 策略

渐进式，分三批 PR，优先处理被多处复制的共同逻辑。

### 批次 1：Conversation + Message 工厂方法

目标：减少 `api/conversations.py`（840 行）中的 SQL 拼装逻辑。

```python
# db/models/conversation.py
class Conversation(Base):
    @classmethod
    def create(cls, user_id: UUID, title: str = "New Conversation") -> "Conversation":
        """封装创建规则，替代散落在 API 层的 Conversation(user_id=...) 调用。"""
        return cls(id=uuid4(), user_id=user_id, title=title, created_at=utcnow())

    def activate_leaf(self, message_id: UUID) -> None:
        """设置活跃叶节点，含校验逻辑。"""
        self.active_leaf_id = message_id

    def update_title(self, title: str) -> None:
        self.title = title
        self.updated_at = utcnow()

class Message(Base):
    @classmethod
    def create(
        cls,
        conversation_id: UUID,
        role: str,
        content: str,
        parent_id: UUID | None = None,
    ) -> "Message":
        return cls(
            id=uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            parent_id=parent_id,
            created_at=utcnow(),
        )
```

### 批次 2：Workflow 状态机方法

```python
class Workflow(Base):
    @classmethod
    def create(cls, user_id: UUID, name: str, dsl: dict) -> "Workflow":
        return cls(id=uuid4(), user_id=user_id, name=name, dsl=dsl)

class WorkflowRun(Base):
    @classmethod
    def start(cls, workflow_id: UUID, user_id: UUID) -> "WorkflowRun":
        return cls(id=uuid4(), workflow_id=workflow_id, user_id=user_id,
                   status="running", started_at=utcnow())

    def complete(self, output: str) -> None:
        self.status = "completed"
        self.output = output
        self.finished_at = utcnow()

    def fail(self, error: str) -> None:
        self.status = "failed"
        self.error = error
        self.finished_at = utcnow()
```

### 批次 3：UserSettings 加密方法内移

```python
class UserSettings(Base):
    def get_api_key(self, provider: str, fernet: Fernet) -> str | None:
        """解密并返回指定 provider 的 API key。替代 core/security.py 中的散落调用。"""
        ...

    def set_api_key(self, provider: str, key: str, fernet: Fernet) -> None:
        """加密并存储 API key。"""
        ...
```

### 约束

- 不改变数据库 schema（无需新 migration）
- 所有工厂方法是纯 Python，不依赖 SQLAlchemy session
- API 层逐步迁移，两种写法在过渡期可共存

---

## 执行顺序与依赖关系

```
P4（1天，无依赖）─────────────────────────────────────────→ merge
P2（1-2天，无依赖）──────────────────────────────────────→ merge
P1（3-5天，建议在P2后执行以利用新 interfaces.py）──────→ merge
P3（1周，建议在P1后执行以测试新服务边界）───────────────→ merge
P5（2-3周，建议在P1后执行以利用清晰的服务层）──────────→ merge（3个PR）
```

---

## 成功标准

| 指标 | 当前 | 目标 |
|------|------|------|
| `chat_stream()` 行数 | 472 | ≤50 |
| `create_graph()` 参数数 | 17 | 2 |
| Agent 执行代码副本数 | 3 | 1 |
| 无测试的关键模块数 | 13 | 0 |
| 循环依赖数 | 1 | 0 |
| Brooks-Lint 健康分 | 42 | ≥85 |
