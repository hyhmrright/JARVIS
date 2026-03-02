# JARVIS Phase 8+ Roadmap — 从 AI 助手到生产级平台

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 将 JARVIS 从单用户本地 AI 助手升级为可部署、可管理、可扩展的多用户 AI 平台。

**当前已完成（Phase 1-7）：**
- Phase 1: RAG 集成 + Agent 工具增强
- Phase 2: Shell / Browser / Sandbox 执行
- Phase 3: 多渠道网关（Telegram / Discord）
- Phase 4: 多 Agent 编排（sessions / 压缩 / subagent / supervisor）
- Phase 5: RAG × Agent 集成 + Skills 系统
- Phase 6: Voice / Canvas / MCP / Cron / Webhook / Dashboard
- Phase 7: Plugin SDK

**技术栈：** Python 3.13, FastAPI, LangGraph, SQLAlchemy async, Vue 3, TypeScript, Pinia, Docker

---

## Phase 8: Bug Fixes & Technical Debt

**分支：** `fix/tech-debt-cleanup`
**优先级：** 高（先还债再加功能）

### Task 8.1: Fix sys.modules Ghost Entry in Plugin Loader

**问题：** `loader.py` 的 `_load_module_file` 中 `sys.modules[namespaced] = module` 在 `exec_module` 之前执行。如果 `exec_module` 抛异常，半初始化的 module stub 永久残留在 `sys.modules` 中，影响后续热重载。

**修改文件：**
- `backend/app/plugins/loader.py` — `_load_module_file` 的 `except` 块中加 `sys.modules.pop(namespaced, None)`
- `backend/tests/test_plugins.py` — 新增测试验证失败加载后 `sys.modules` 中无残留

**实现：**
```python
# loader.py _load_module_file except block
except Exception:
    logger.exception("plugin_module_load_failed", path=str(path))
    sys.modules.pop(namespaced, None)  # Clean up ghost entry
    return
```

**测试：**
```python
def test_failed_module_load_cleans_sys_modules(tmp_path: Path) -> None:
    """Failed exec_module should not leave ghost entry in sys.modules."""
    bad_plugin = tmp_path / "bad_plugin.py"
    bad_plugin.write_text("raise RuntimeError('intentional')")
    reg = PluginRegistry()
    _load_module_file(bad_plugin, reg)
    assert "jarvis_user_plugins.bad_plugin" not in sys.modules
```

### Task 8.2: Gateway `_run_agent` 错误恢复

**问题：** `gateway/agent_runner.py` 中如果 `create_graph().ainvoke()` 抛异常，用户只收到一个静默失败，没有错误提示。

**修改文件：**
- `backend/app/gateway/agent_runner.py` — `_run_agent` 加 try/except，异常时返回友好错误消息
- `backend/tests/gateway/test_agent_runner.py` — 测试异常场景

### Task 8.3: chat.py Plugin Tools 预过滤（对齐 MCP 行为）

**问题：** `chat.py` 中 MCP tools 有 `enabled_tools` 预过滤（避免不必要的加载），但 plugin tools 始终无条件加载并传递给 `create_graph`。虽然 `_resolve_tools` 内部会过滤，但资源浪费。

**修改文件：**
- `backend/app/api/chat.py` — plugin_tools 加同样的预过滤 guard
- `backend/app/gateway/agent_runner.py` — 同步修改

**实现：**
```python
# chat.py generate() 内
plugin_tools_list: list = []
if llm.enabled_tools is None or "plugin" in llm.enabled_tools:
    plugin_tools_list = plugin_registry.get_all_tools() or []
# ...
graph = create_graph(..., plugin_tools=plugin_tools_list or None)
```

---

## Phase 9: RBAC & Admin Panel

**分支：** `feature/phase9-rbac-admin`
**优先级：** 高（多用户部署的前提）

### Task 9.1: User Roles Model

**新建文件：**
- `backend/alembic/versions/XXX_add_user_roles.py`

**修改文件：**
- `backend/app/db/models.py` — `User` 表新增 `role` 列（enum: `user` / `admin` / `superadmin`，default=`user`）

**设计：**
```python
class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"

# User model 新增
role: Mapped[str] = mapped_column(String(20), default=UserRole.USER.value)
```

### Task 9.2: Admin Permission Guard

**新建文件：**
- `backend/app/api/deps.py` — 新增 `get_admin_user` dependency（检查 role >= admin）

**实现：**
```python
async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role not in (UserRole.ADMIN.value, UserRole.SUPERADMIN.value):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
```

### Task 9.3: Admin API — User Management

**新建文件：**
- `backend/app/api/admin.py`
- `backend/tests/api/test_admin.py`

**端点：**
- `GET /api/admin/users` — 列出所有用户（分页）
- `PATCH /api/admin/users/{id}` — 修改用户角色 / 禁用用户
- `DELETE /api/admin/users/{id}` — 软删除用户
- `GET /api/admin/stats` — 系统统计（用户数、消息数、token 用量）

### Task 9.4: Admin API — Plugin Management

**修改文件：**
- `backend/app/api/plugins.py` — 新增 admin 端点

**端点：**
- `POST /api/admin/plugins/{id}/enable` — 全局启用/禁用插件
- `GET /api/admin/plugins/config` — 获取插件全局配置

### Task 9.5: Frontend Admin Page

**新建文件：**
- `frontend/src/pages/AdminPage.vue`
- `frontend/src/api/admin.ts`

**修改文件：**
- `frontend/src/router/index.ts` — 新增 `/admin` 路由（仅 admin 角色可见）
- `frontend/src/locales/*.json` — 6 种语言的 admin 相关翻译

**设计：**
- Tab 布局：Users | Plugins | System Stats
- Users tab: 表格列出用户，支持角色修改和禁用操作
- Plugins tab: 已安装插件列表，全局开关
- Stats tab: 用户数、消息数、token 消耗趋势图（复用 UsagePage 的图表组件）

---

## Phase 10: 更多渠道接入

**分支：** `feature/phase10-more-channels`
**优先级：** 中

### Task 10.1: Slack Channel

**新建文件：**
- `backend/app/gateway/channels/slack.py`
- `backend/tests/gateway/test_slack_channel.py`

**依赖：** `slack-bolt` (async)

**设计：**
- 使用 Slack Bolt framework（async mode）
- Socket Mode 连接（无需公网 URL）
- 支持 `@JARVIS` mention 触发
- 消息分块：Slack 4000 字符限制
- 注册到 `ChannelRegistry`

### Task 10.2: 飞书（Lark）Channel

**新建文件：**
- `backend/app/gateway/channels/lark.py`
- `backend/tests/gateway/test_lark_channel.py`

**设计：**
- 使用飞书 Open API（Webhook 模式 + 长连接模式可选）
- 消息加密验证（AES-256-CBC）
- 支持群组 @机器人 触发
- 富文本回复（Markdown → Lark card）

### Task 10.3: 微信公众号 Channel

**新建文件：**
- `backend/app/gateway/channels/wechat.py`
- `backend/tests/gateway/test_wechat_channel.py`

**设计：**
- 使用微信公众平台 API
- XML 消息解析 + 加密/解密
- 被动回复（5 秒限制）→ 超时回复"正在思考…" + 客服消息异步推送
- 注意：需公众号服务号（订阅号无客服消息权限）

### Task 10.4: 统一 Channel 配置

**修改文件：**
- `backend/app/core/config.py` — 新增 channel 配置项
- `backend/app/main.py` — lifespan 中按配置启动已启用的 channels

**设计：**
```python
# .env
ENABLED_CHANNELS=telegram,discord,slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
LARK_APP_ID=cli_...
LARK_APP_SECRET=...
WECHAT_APP_ID=wx...
WECHAT_APP_SECRET=...
WECHAT_TOKEN=...
WECHAT_ENCODING_AES_KEY=...
```

---

## Phase 11: 前端体验升级

**分支：** `feature/phase11-frontend-ux`
**优先级：** 中

### Task 11.1: WebSocket 实时通信

**修改文件：**
- `backend/app/api/chat.py` — 新增 `/api/chat/ws` WebSocket 端点
- `frontend/src/stores/chat.ts` — WebSocket 连接管理（fallback 到 SSE）

**设计：**
- WebSocket 用于双向通信（中断生成、实时状态）
- SSE 作为降级方案保留
- 前端自动检测并选择最佳传输方式

### Task 11.2: 对话分支 & 重新生成

**修改文件：**
- `backend/app/db/models.py` — `Message` 新增 `parent_id` 列（nullable self-FK）
- `backend/app/api/chat.py` — 新增 `POST /api/chat/regenerate` 端点
- `frontend/src/pages/ChatPage.vue` — 消息气泡新增"重新生成"按钮

**设计：**
- 重新生成 = 从同一 parent 创建新分支
- 前端展示切换箭头（← 1/3 →）在同级回复间切换
- 历史加载时按 `parent_id` 构建树，展示当前活跃分支

### Task 11.3: 文件上传到对话

**修改文件：**
- `frontend/src/pages/ChatPage.vue` — 输入框支持拖拽/粘贴文件
- `backend/app/api/chat.py` — 新增 multipart 消息处理
- `backend/app/tools/file_tool.py` — 扩展支持对话内文件引用

**设计：**
- 支持图片、PDF、代码文件
- 图片：base64 编码传给 vision-capable 模型
- 其他文件：提取文本作为上下文注入

### Task 11.4: 暗色主题

**修改文件：**
- `frontend/src/App.vue` — 主题切换逻辑
- `frontend/src/stores/` — 新增 `theme.ts` store
- `frontend/tailwind.config.ts` — dark mode 配置

### Task 11.5: 移动端适配优化

**修改文件：**
- `frontend/src/pages/ChatPage.vue` — 响应式布局优化
- `frontend/src/components/` — 侧边栏抽屉模式（移动端）

---

## Phase 12: 安全加固 & 生产就绪

**分支：** `feature/phase12-production-ready`
**优先级：** 高（部署前必须）

### Task 12.1: API Rate Limiting 增强

**修改文件：**
- `backend/app/core/rate_limit.py` — 按端点、按用户、按 IP 的多层限速
- `backend/app/api/chat.py` — chat stream 端点加限速

**设计：**
- Redis 滑动窗口算法
- 全局：100 req/min per IP
- 认证用户：30 req/min per user for chat
- Admin：无限制

### Task 12.2: Input Sanitization & Prompt Injection Defense

**新建文件：**
- `backend/app/core/sanitizer.py`
- `backend/tests/core/test_sanitizer.py`

**设计：**
- 用户输入长度限制（已有 50000 字符限制，检查是否足够）
- Tool output sanitization（防止 tool 返回恶意 prompt）
- System prompt 保护（禁止用户通过输入覆盖 system prompt）

### Task 12.3: Audit Log

**新建文件：**
- `backend/app/db/models.py` — `AuditLog` 模型
- `backend/app/core/audit.py` — 审计日志记录器
- `backend/app/api/admin.py` — 新增 `GET /api/admin/audit-logs` 端点

**设计：**
```python
class AuditLog(Base):
    id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID | None]  # None for system events
    action: Mapped[str]  # "user.login", "tool.execute", "admin.role_change"
    resource_type: Mapped[str]  # "user", "conversation", "plugin"
    resource_id: Mapped[str | None]
    details_json: Mapped[dict | None]  # JSONB
    ip_address: Mapped[str | None]
    created_at: Mapped[datetime]
```

### Task 12.4: API Key Scope & Rotation

**修改文件：**
- `backend/app/db/models.py` — 新增 `APIKey` 模型（支持多 key、scope、expiry）
- `backend/app/api/auth.py` — 新增 API key 认证方式（除 JWT 外）

**设计：**
- 支持 Bearer token（JWT）和 API key（`X-API-Key` header）两种认证
- API key 支持 scope（`chat:read`, `chat:write`, `admin:*`）
- API key 支持过期时间

### Task 12.5: Docker 多阶段构建优化

**修改文件：**
- `backend/Dockerfile` — 多阶段构建：builder → runtime
- `frontend/Dockerfile` — 多阶段构建：builder → nginx
- `docker-compose.yml` — healthcheck 完善

**目标：**
- 后端镜像：< 200MB（当前约 800MB）
- 前端镜像：< 50MB（nginx + static files）

---

## Phase 13: 插件市场 & 扩展生态

**分支：** `feature/phase13-plugin-marketplace`
**优先级：** 低（生态建设）

### Task 13.1: Plugin Manifest

**修改文件：**
- `backend/app/plugins/sdk.py` — `JarvisPlugin` 新增 manifest 属性

**设计：**
```python
class JarvisPlugin(ABC):
    # 已有
    plugin_id: str
    plugin_name: str
    plugin_description: str = ""
    plugin_version: str = "0.1.0"

    # 新增
    plugin_author: str = ""
    plugin_homepage: str = ""
    plugin_license: str = ""
    plugin_requires: list[str] = []  # 依赖的其他插件
    plugin_config_schema: dict | None = None  # JSON Schema for config
```

### Task 13.2: Plugin Config UI

**修改文件：**
- `backend/app/api/plugins.py` — `GET/PUT /api/plugins/{id}/config`
- `frontend/src/pages/SettingsPage.vue` — 插件配置表单（根据 JSON Schema 动态渲染）

### Task 13.3: Plugin Hot Reload

**修改文件：**
- `backend/app/plugins/loader.py` — `reload_plugin(plugin_id)` 函数
- `backend/app/api/plugins.py` — `POST /api/admin/plugins/{id}/reload`

**设计：**
- 卸载旧 plugin → 清理 sys.modules → 重新加载 → 激活
- 仅 admin 可操作

---

## Phase 14: CI/CD & E2E 测试

**分支：** `feature/phase14-cicd-e2e`
**优先级：** 中

### Task 14.1: Playwright E2E Tests

**新建文件：**
- `frontend/e2e/login.spec.ts`
- `frontend/e2e/chat.spec.ts`
- `frontend/e2e/documents.spec.ts`
- `frontend/playwright.config.ts`

**设计：**
- 登录流程 → 创建会话 → 发送消息 → 验证 SSE 响应
- 文档上传 → RAG 搜索验证
- 设置页面 → 工具开关 → 验证 agent 行为

### Task 14.2: GitHub Actions 完善

**修改文件：**
- `.github/workflows/ci.yml` — 增加 E2E 测试 job
- `.github/workflows/release.yml` — Docker 镜像构建 + 发布到 GHCR

### Task 14.3: 自动化部署脚本

**新建文件：**
- `scripts/deploy.sh` — 一键部署（拉取镜像、迁移数据库、重启服务）
- `scripts/backup.sh` — 数据库 + MinIO 备份

---

## 执行顺序建议

| 顺序 | Phase | 预估工作量 | 依赖 |
|------|-------|-----------|------|
| 1 | Phase 8（Tech Debt） | 0.5 天 | 无 |
| 2 | Phase 12（安全加固） | 2 天 | 无 |
| 3 | Phase 9（RBAC & Admin） | 2 天 | 无 |
| 4 | Phase 11（前端 UX） | 3 天 | 无 |
| 5 | Phase 10（更多渠道） | 2 天 | Phase 9（admin 管理） |
| 6 | Phase 14（CI/CD & E2E） | 1 天 | Phase 11（前端页面） |
| 7 | Phase 13（插件市场） | 2 天 | Phase 9（admin） |

**推荐先做 Phase 8 → 12 → 9**，把基础打好再扩展功能。

---

## 验证清单

每个 Phase 完成后必须通过：

1. `cd backend && uv run ruff check --fix && uv run ruff format` — lint
2. `cd backend && uv run mypy app` — type check
3. `cd frontend && bun run lint:fix && bun run type-check` — 前端检查
4. `cd backend && uv run pytest tests/ -v` — 全量测试
5. `docker compose up -d && docker compose ps` — 全栈启动验证
6. `pre-commit run --all-files` — hooks
