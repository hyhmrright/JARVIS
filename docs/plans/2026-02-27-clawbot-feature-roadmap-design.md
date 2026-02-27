# JARVIS 全能本地助手 Feature Roadmap

> 基于 OpenClaw 项目分析，结合 JARVIS 现有架构（Python/FastAPI/LangGraph/Vue 3）的完整功能演进规划。

## 背景

OpenClaw 是一个本地优先的 AI 助手平台，通过 WebSocket Gateway 统一接入 15+ 消息平台，让 AI agent 能在用户设备上执行 Shell 命令、控制浏览器、管理文件，并通过 Docker 沙箱隔离。其核心优势：全渠道消息路由、真实计算机控制、多 Agent 编排、Skills-as-Markdown 插件系统、语音唤醒。

JARVIS 当前是一个 Web-only 的 AI 对话平台，具备 RAG 管线（未接入对话）、多 LLM 支持（DeepSeek/OpenAI/Anthropic/ZhipuAI）、流式 SSE 对话、Vue 3 前端和 Docker 全栈部署。本规划旨在将 JARVIS 演进为全能本地助手。

## 设计原则

1. **渐进式交付**：每个 Phase 可独立交付用户价值
2. **Python 生态优先**：充分利用 Python 异步生态（aiogram/discord.py/playwright）
3. **保持架构一致**：沿用 FastAPI + LangGraph + Pinia 的现有风格
4. **安全第一**：借鉴 OpenClaw 的沙箱隔离和权限控制理念
5. **YAGNI**：不过度设计，按需扩展

---

## Phase 1: 核心补齐 — RAG 接入 + Agent 工具增强

**交付价值**: 让现有 AI 对话真正有用，从"聊天机器人"进化为"智能助手"

### 1.1 RAG 接入对话流

- **现状**: RAG 管线已实现（文档上传 → 分块 → Embedding → Qdrant），但检索结果未接入 Agent 对话
- **目标**: LangGraph agent 调用 RAG 检索工具，基于知识库回答问题
- **设计**:
  - 新增 `tools/rag_search.py`，封装 Qdrant 相似度查询
  - Tool 签名：`rag_search(query: str, top_k: int = 5) -> list[Document]`
  - Agent system prompt 中加入知识库使用指引
  - 检索结果作为 context 注入，附带来源引用
- **对标 OpenClaw**: memory tool + web_search 的结合

### 1.2 Web Search 工具

- **目标**: Agent 可主动搜索互联网获取实时信息
- **设计**:
  - 新增 `tools/web_search.py`
  - 支持 Tavily（推荐，有 LangChain 集成）/ SerpAPI / Brave Search
  - API key 通过 user_settings 表配置（Fernet 加密）
  - Tool 签名：`web_search(query: str, max_results: int = 5) -> list[SearchResult]`
- **对标 OpenClaw**: `web_search` tool (Brave API)

### 1.3 Web Fetch 工具

- **目标**: Agent 可抓取指定 URL 的网页内容
- **设计**:
  - 新增 `tools/web_fetch.py`
  - 使用 `httpx` + `readability-lxml` 或 `trafilatura` 提取正文
  - 内容截断策略：超过 token 限制时自动摘要
  - Tool 签名：`web_fetch(url: str) -> WebContent`
- **对标 OpenClaw**: `web_fetch` tool (Firecrawl/readability)

### 1.4 流式 Tool 调用状态展示

- **现状**: SSE 流只传输文本 token
- **目标**: 流式中显示 tool 调用过程（搜索中/读取中等状态）
- **设计**:
  - SSE 事件扩展：`tool_start`/`tool_end` 事件类型
  - 前端 chat store 解析 tool 事件，显示状态卡片
  - 工具执行结果可折叠展示
- **对标 OpenClaw**: tool stream display (`app-tool-stream.ts`)

### 1.5 Auth Profile 轮转

- **现状**: 单个 API key per provider
- **目标**: 支持多 API key 配置 + 自动故障转移
- **设计**:
  - `user_settings` 表扩展：每个 provider 支持多个 API key
  - LLM 工厂 (`agent/llm.py`) 增加重试逻辑：key 失败 → 切换下一个 → cooldown
  - 设置页面 UI 支持添加/删除多个 key
- **对标 OpenClaw**: auth profile rotation with cooldown

---

## Phase 2: Agent 执行能力 — Shell + 浏览器 + 沙箱

**交付价值**: AI 能在用户机器上真正执行任务，不只是聊天

### 2.1 Shell 执行 Tool

- **目标**: Agent 可执行 shell 命令
- **设计**:
  - 新增 `tools/shell_exec.py`
  - 使用 `asyncio.create_subprocess_exec`（避免 shell 注入）
  - 安全限制：命令白名单/黑名单、执行超时（默认 30s）、输出长度限制
  - Tool 签名：`shell_exec(command: str, timeout: int = 30) -> ShellResult`
  - 前端显示命令和输出（带语法高亮）
- **对标 OpenClaw**: `exec` tool

### 2.2 Docker 沙箱

- **目标**: 代码执行在隔离容器中运行
- **设计**:
  - 新增 `Dockerfile.sandbox`：基础 Python/Node 环境
  - 沙箱模式：`off`（直接执行）/ `on`（容器执行）
  - 使用 Docker SDK for Python (`docker` 库) 管理容器生命周期
  - 工作区挂载：只读（默认）/ 读写（需用户确认）
  - 资源限制：CPU/内存/磁盘配额
  - 容器池 + 空闲回收
- **对标 OpenClaw**: sandbox system (session/agent/shared scopes)

### 2.3 浏览器自动化 Tool

- **目标**: Agent 可控制浏览器执行操作
- **设计**:
  - 新增 `tools/browser.py`
  - 使用 `playwright` Python SDK（async API）
  - 操作：navigate / click / type / screenshot / extract_text / fill_form / evaluate
  - 浏览器在沙箱容器中运行（headless Chrome）
  - 截屏结果可通过 MinIO 存储并在前端展示
- **对标 OpenClaw**: `browser` tool (Playwright CDP)

### 2.4 文件读写 Tool

- **目标**: Agent 可读写工作区文件
- **设计**:
  - 新增 `tools/file_ops.py`
  - 操作：read_file / write_file / list_dir / search_files
  - 路径限制：只能访问用户工作区目录（`/workspace/{user_id}/`）
  - 在沙箱模式下映射到容器内路径
- **对标 OpenClaw**: `read`/`write`/`edit`/`find` tools

### 2.5 执行权限控制

- **目标**: 按工具危险等级设置权限策略
- **设计**:
  - 权限级别：`auto`（自动执行）/ `ask`（需用户确认）/ `deny`（禁用）
  - 默认策略：RAG/search = auto, shell/file = ask, browser = ask
  - 用户可在设置页面自定义每个 tool 的策略
  - 前端实现确认对话框（工具调用时暂停等待确认）
- **对标 OpenClaw**: ask policies + elevated access

---

## Phase 3: 多渠道接入 — Gateway + 消息平台

**交付价值**: AI 助手不只在 Web 上，还能在 Telegram/Discord 等常用平台使用

### 3.1 Gateway 层

- **目标**: 统一消息路由和 session 管理
- **设计**:
  - 新增 `app/gateway/` 模块
  - 核心组件：`router.py`（消息路由）、`session_manager.py`（session 生命周期）、`channel_registry.py`（频道注册）
  - 消息模型：统一 `GatewayMessage`（sender, channel, content, attachments, metadata）
  - 使用 Redis pub/sub 做跨进程路由（多 worker 场景）
  - FastAPI WebSocket endpoint 提供控制面板接口
- **对标 OpenClaw**: Gateway server (WebSocket control plane)

### 3.2 频道适配器抽象

- **目标**: 统一接口，新增频道只需实现适配器
- **设计**:
  - 定义 `ChannelAdapter` 抽象基类
  - 方法：`start()`, `stop()`, `send_message()`, `on_message()`
  - 频道配置通过 `user_settings` 或独立的 `channel_configs` 表
  - 每个频道适配器作为独立的 asyncio task 运行
- **对标 OpenClaw**: ChannelPlugin SDK

### 3.3 Telegram 频道

- **目标**: 通过 Telegram Bot 使用 JARVIS
- **设计**:
  - 使用 `aiogram` v3（成熟的异步 Telegram 框架）
  - 支持：文本消息、图片/文件、Markdown 格式、内联按钮
  - Bot token 通过设置页面配置
  - 消息路由到对应用户的 Agent session
- **对标 OpenClaw**: Telegram channel (grammY)

### 3.4 Discord 频道

- **目标**: 通过 Discord Bot 使用 JARVIS
- **设计**:
  - 使用 `discord.py`（成熟的异步 Discord 框架）
  - 支持：文本消息、Embed、Slash commands、Thread
  - Bot token 和 guild 配置通过设置页面
- **对标 OpenClaw**: Discord channel (discord.js)

### 3.5 微信频道（JARVIS 特色）

- **目标**: 通过微信使用 JARVIS（OpenClaw 不支持）
- **设计**:
  - 使用 WeChatFerry 或 ComWeChatBot SDK
  - 限制：微信生态限制较多，需要运行在 Windows 上或使用 Wine
  - 作为可选功能，不影响主架构
- **对标 OpenClaw**: 无（JARVIS 特色功能）

### 3.6 DM 安全策略

- **目标**: 防止未授权用户滥用 Bot
- **设计**:
  - 配对码验证：未知用户首次发消息需输入配对码
  - 管理员审核模式：新用户需管理员批准
  - 频率限制：已有的 rate limiting 扩展到频道层面
- **对标 OpenClaw**: dmPolicy="pairing"

---

## Phase 4: Multi-Agent 编排

**交付价值**: 复杂任务自动拆分、并行执行

### 4.1 Session 管理增强

- **目标**: 独立 session 隔离上下文
- **设计**:
  - Session 模型：`{session_id, user_id, agent_type, parent_session_id, context, status, created_at}`
  - 主 session（对话）+ 子 session（subagent）
  - Session 生命周期：created → active → completed/aborted
  - Redis 存储活跃 session 状态

### 4.2 SubAgent 生成

- **目标**: 主 Agent 可生成子 Agent 执行子任务
- **设计**:
  - 新增 `tools/subagent.py`
  - Tool 签名：`spawn_subagent(task: str, model: str | None = None, timeout: int = 300) -> SubAgentResult`
  - 子 Agent 拥有独立 LangGraph 实例和上下文
  - 结果回传给主 Agent
  - 深度限制（默认 max_depth=3）
- **对标 OpenClaw**: `sessions_spawn`

### 4.3 跨 Session 通信

- **目标**: Agent 间可发消息、查历史
- **设计**:
  - `sessions_send(session_id: str, message: str)` — 向指定 session 发消息
  - `sessions_history(session_id: str)` — 获取指定 session 历史
  - 通过 Redis pub/sub 实现异步通信
- **对标 OpenClaw**: `sessions_send`/`sessions_history`

### 4.4 Context 压缩

- **目标**: 长对话自动压缩，防止 token 溢出
- **设计**:
  - 检测 token 使用率，接近阈值时触发压缩
  - 压缩策略：调用 LLM 生成对话摘要，替换早期消息
  - 保留最近 N 条消息 + 摘要前缀
  - 压缩后的摘要存入 messages 表（type=summary）
- **对标 OpenClaw**: compaction system

### 4.5 任务编排（Supervisor 模式）

- **目标**: 复杂任务自动拆分、分发、汇总
- **设计**:
  - LangGraph 升级：Supervisor node 接收任务 → 拆分子任务 → 分发给 SubAgent → 汇总结果
  - 可视化：前端显示任务拆分树和执行进度
  - 自定义编排模板（Agent 组合配置）
- **对标 OpenClaw**: multi-agent orchestration

---

## Phase 5: 插件系统 + Skills 平台

**交付价值**: 社区可扩展 JARVIS，agent 行为可定制

### 5.1 Plugin SDK

- **目标**: Python 插件接口
- **设计**:
  - 新增 `app/plugins/` 模块
  - 定义 `JarvisPlugin` 抽象基类（plugin_id, plugin_name, on_load, on_unload）
  - 注册点：tool / channel / memory_backend
  - 插件发现：扫描 `plugins/` 目录中的 Python 包
  - 插件隔离：独立虚拟环境或 importlib 沙箱
- **对标 OpenClaw**: Plugin SDK

### 5.2 Skills 即 Markdown

- **目标**: 纯 Markdown 文件定义 Agent 行为
- **设计**:
  - Skill 格式：YAML frontmatter（name/description/triggers）+ Markdown body（指令/模板）
  - 存放路径：`~/.jarvis/skills/` 或项目 `skills/` 目录
  - Agent system prompt 动态注入可用 skills 列表
  - Agent 按需读取 skill 内容并遵循指令
- **对标 OpenClaw**: Skills platform (SKILL.md files)

### 5.3 Cron 定时任务

- **目标**: Agent 可设置和管理定时任务
- **设计**:
  - 新增 `tools/cron.py` 和 `app/scheduler/` 模块
  - 使用 APScheduler（Python 异步调度库）
  - Tool 签名：`cron_set(schedule: str, task: str)` / `cron_list()` / `cron_delete(id: str)`
  - 任务持久化到数据库（`cron_jobs` 表）
  - 触发时创建新 session 执行任务
- **对标 OpenClaw**: cron tool

### 5.4 Webhook 接入

- **目标**: 外部事件触发 Agent
- **设计**:
  - 新增 `/api/webhooks/{webhook_id}` endpoint
  - 用户可创建 webhook（绑定到 agent + 指令模板）
  - 支持 GitHub webhook、邮件通知等
  - Webhook 触发时创建新 session 处理事件
- **对标 OpenClaw**: webhook system

### 5.5 MCP Server 支持

- **目标**: 作为 MCP client 连接外部 MCP server
- **设计**:
  - 集成 `mcp` Python SDK
  - 自动将 MCP server 提供的 tools 注册为 LangGraph tools
  - 配置方式：设置页面添加 MCP server endpoint
  - 支持 stdio 和 HTTP 两种传输方式
- **对标 OpenClaw**: mcporter (MCP integration)

---

## Phase 6: 终端体验 — 语音 + Canvas + 移动端

**交付价值**: 从文字聊天进化为全感官助手

### 6.1 TTS 语音回复

- **目标**: Agent 回复可用语音播放
- **设计**:
  - 后端新增 `/api/tts/synthesize` endpoint
  - 支持 ElevenLabs API / Edge TTS（免费）/ 本地 sherpa-onnx
  - 前端 Audio 播放组件
  - 用户可选择语音和语速
- **对标 OpenClaw**: TTS pipeline

### 6.2 语音输入

- **目标**: Web 前端支持语音输入
- **设计**:
  - 方案 A：浏览器 Web Speech API（零成本，兼容性一般）
  - 方案 B：Whisper API（OpenAI/本地 faster-whisper）
  - 前端添加麦克风按钮，录音 → 转文字 → 发送
- **对标 OpenClaw**: Voice Wake

### 6.3 Live Canvas

- **目标**: Agent 可向前端推送实时交互式 UI
- **设计**:
  - 前端新增 Canvas 容器组件（iframe sandbox）
  - Agent tool：`canvas_render(html: str)` 推送 HTML/CSS/JS
  - WebSocket 实时更新 canvas 内容
  - 用例：数据可视化、表单生成、代码预览
- **对标 OpenClaw**: Canvas + A2UI

### 6.4 移动端适配

- **目标**: 移动端可用的 JARVIS 体验
- **设计**:
  - 方案 A：PWA（最低成本，通知受限）
  - 方案 B：Capacitor 打包（原生能力，维护成本中等）
  - 响应式 UI 改造（chat 页面优先）
- **对标 OpenClaw**: iOS/Android apps

### 6.5 Usage 仪表盘

- **目标**: Token 用量和成本统计可视化
- **设计**:
  - 后端记录每次 LLM 调用的 token 用量
  - 新增 `token_usage` 表（session_id, model, prompt_tokens, completion_tokens, cost, timestamp）
  - 前端新增 Usage 页面：日/周/月用量图表、按模型分布、成本估算
  - 利用现有 Grafana 基础设施做可选的高级监控
- **对标 OpenClaw**: usage metrics

---

## 技术架构总览

```
                     ┌──────────────────────────────────────────┐
                     │              Frontend (Vue 3)             │
                     │  Chat | Documents | Settings | Canvas     │
                     │  Usage | Skills | Channels | Cron         │
                     └────────────────┬─────────────────────────┘
                                      | HTTP/SSE/WebSocket
                     ┌────────────────┴─────────────────────────┐
                     │          Gateway (FastAPI)                 │
                     │  ┌─────────┐ ┌──────────┐ ┌───────────┐  │
                     │  │ Router  │ │ Sessions │ │ Channels  │  │
                     │  └────┬────┘ └────┬─────┘ └─────┬─────┘  │
                     │       │           │             │         │
                     │  ┌────┴───────────┴─────────────┴────┐   │
                     │  │        LangGraph Agent              │   │
                     │  │  ┌─────┐ ┌──────┐ ┌─────────────┐  │   │
                     │  │  │Tools│ │Skills│ │ SubAgents   │  │   │
                     │  │  └──┬──┘ └──────┘ └─────────────┘  │   │
                     │  └─────┼──────────────────────────────┘   │
                     │        │                                   │
                     │  ┌─────┴──────────────────────────────┐   │
                     │  │          Tool Surface                │   │
                     │  │ RAG | Search | Fetch | Shell | File  │   │
                     │  │ Browser | Cron | SubAgent | MCP      │   │
                     │  └─────────────────────────────────────┘   │
                     │                                             │
                     │  ┌──────────────────────────────────────┐   │
                     │  │          Plugin System                │   │
                     │  │  Channel | Tool | Memory | Skill      │   │
                     │  └──────────────────────────────────────┘   │
                     └─────────────────────────────────────────────┘
                              │         │         │
               ┌──────────────┼─────────┼─────────┼──────────────┐
               │              │         │         │              │
          ┌────┴───┐   ┌─────┴──┐  ┌───┴───┐ ┌───┴────┐  ┌─────┴──┐
          │Postgres│   │ Qdrant │  │ Redis │ │ MinIO  │  │ Docker │
          │  (DB)  │   │ (RAG)  │  │(Cache)│ │(Files) │  │Sandbox │
          └────────┘   └────────┘  └───────┘ └────────┘  └────────┘

     External Channels:
     ┌──────────┐ ┌─────────┐ ┌────────┐ ┌────────┐
     │ Telegram │ │ Discord │ │ WeChat │ │ WebChat│
     └──────────┘ └─────────┘ └────────┘ └────────┘
```

## 实施时间线建议

| Phase | 预估工作量 | 关键依赖 |
|-------|----------|---------|
| Phase 1: 核心补齐 | 中等 | 无，可立即开始 |
| Phase 2: 执行能力 | 大 | Phase 1 完成 |
| Phase 3: 多渠道 | 大 | Phase 1 完成 |
| Phase 4: Multi-Agent | 大 | Phase 2 完成 |
| Phase 5: 插件系统 | 中等 | Phase 2-3 完成 |
| Phase 6: 终端体验 | 中等 | Phase 1 完成 |

Phase 2 和 Phase 3 可以并行开发。Phase 6 的部分功能（TTS、语音输入、Usage 仪表盘）可以提前到任何阶段。
