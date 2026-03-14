# JARVIS 最终完善计划 (Phase 13-14)

## 目标
完成 JARVIS 项目路线图中剩余的核心功能，包括微信渠道、对话分支、WebSocket、插件动态配置以及端到端测试，实现真正的生产级满血版平台。由于任务庞大，我们将项目拆解为 4 个独立且可以并行或逐步推进的子项目（Sub-projects）。

---

## 阶段 1：对话核心体验升级 (Chat Branching & WebSocket)
**目标**：重构底层消息结构，支持主流 AI 助手的树状对话历史（重新生成 / 多版本回复），并利用 WebSocket 提升连接稳定性。

1. **数据库升级 (Alembic)**: 
   - 修改 `Message` 模型，新增 `parent_id` (UUID, nullable, self-referencing ForeignKey)。
   - 编写迁移脚本处理历史存量数据（将线性的消息链转化为 `parent_id` 相连的链表）。
2. **后端 API (FastAPI)**:
   - 新增 `POST /api/chat/regenerate`：根据传入的 `message_id`，复用其 `parent_id` 作为起点重新生成回答。
   - 新增 `GET /api/chat/ws`：建立 WebSocket 通信管道，支持双向指令（如客户端发送中断生成指令）。
3. **前端适配 (Vue 3)**:
   - **数据结构**：重构 `chat.ts` 状态库，将线性的消息数组转换为树状结构（或保留当前游标所在的一条路径）。
   - **UI 渲染**：在消息气泡上增加“重新生成”按钮以及版本切换箭头 (← 1/3 →)。
   - **网络层**：增加 WebSocket 连接管理器，保留现有的 SSE 作为降级 (Fallback) 方案。

---

## 阶段 2：微信公众号生态接入 (WeChat Gateway)
**目标**：打通国内最重要的高频触点，支持在微信服务号中直接与 JARVIS 对话。

1. **协议层集成**: 
   - 引入处理微信 XML 格式解析和 AES-256-CBC 消息加解密的库（如 `wechatpy` 或原生实现）。
2. **后端 Channel 实现 (`channels/wechat.py`)**:
   - **Challenge 验证**：处理微信服务器初次绑定的 Token 验证请求。
   - **同步转异步处理**：微信要求 5 秒内必须回复。对于慢速 LLM 推理，需要先同步回复一条“正在思考中…”的占位文本或空串。
   - **异步推送**：后台任务生成完毕后，调用微信“客服消息接口”主动下发文本给用户。
3. **环境与路由注册**:
   - 在 `.env` 和 `core/config.py` 增加 `WECHAT_APP_ID`, `WECHAT_APP_SECRET`, `WECHAT_TOKEN`。
   - 在 `Gateway` 中注册微信 Webhook 端点。

---

## 阶段 3：插件市场与动态配置中心 (Plugin Ecosystem)
**目标**：让第三方插件的使用门槛大幅降低，管理员无需修改环境变量即可在前端页面直接配置插件（如设置 GitHub Token 等）。

1. **Plugin SDK 扩展 (`plugins/sdk.py`)**: 
   - 扩展 `JarvisPlugin` 基类，新增 `plugin_config_schema` (返回标准 JSON Schema) 和 `requires` 字段。
2. **后端 API 与存储**:
   - 利用现有的 `plugin_configs` 数据库表（或新建），提供 `GET /api/plugins/{id}/config` 和 `PUT /api/plugins/{id}/config` 接口。
   - 实现热重载机制：提供 `POST /api/admin/plugins/{id}/reload` 接口，在内存中动态替换 `sys.modules` 的引用。
3. **前端 UI (Admin/Settings Page)**:
   - 引入一个轻量级的 JSON Schema Form 渲染库（例如 `vue-form-schema` 或手写递归组件）。
   - 根据插件返回的 Schema 动态生成输入框，支持密码脱敏显示和验证。

---

## 阶段 4：Playwright 端到端质量保障 (E2E Testing)
**目标**：为整个重构和后续开发建立安全网，防止回归错误。

1. **基建搭建**: 
   - 在 `frontend` 目录执行 `bun create playwright`，配置 `e2e` 目录和 `playwright.config.ts`。
2. **核心业务用例编写**:
   - `auth.spec.ts`: 测试登录、注册拦截与 JWT 续期。
   - `chat.spec.ts`: 模拟用户输入，断言流式返回的 DOM 节点变化以及打字机效果。
   - `rag.spec.ts`: 模拟文件上传，并在后续对话中断言是否成功调用了 `rag_tool`。
3. **CI 集成 (`.github/workflows`)**:
   - 编写新的 Actions 配置文件，启动 Postgres/Redis 容器 -> 启动后端 -> 构建前端 -> 运行 headless Chrome 测试。
