# 规范: OpenClaw 特性对齐 (OpenClaw Feature Alignment)

## 概述 (Overview)
该轨道旨在将 JARVIS 从一个基础的 AI 助手平台提升为一个类似于 OpenClaw 的全能型个人 AI 智能体 (Personal AI Agent)。核心改进点包括：支持通过主流通讯工具交互、提供轻量化的技能定义、集成安全的 Docker 沙箱执行环境、开发可视化交互画布、以及增强自动化能力。

## 功能需求 (Functional Requirements)

### 1. 多渠道消息网关 (Multi-channel Gateway)
- **支持接入 Telegram, 飞书 (Lark), Discord, Slack**。
- 实现一个通用的 `MessageAdapter` 层，用于在 JARVIS 内部消息格式与各平台 API 之间进行转换。
- 支持流式输出在各通讯平台的透传（如果平台 API 支持）。
- 实现跨平台的统一身份识别与状态保持。

### 2. 轻量化技能定义与 Shell 自动化 (Skills & Tools)
- **Skills 存储**：支持在根目录 `/skills/` 下使用 Markdown (`SKILL.md`) 文件定义新技能。
- **动态解析**：实现一个解析器，在 JARVIS 启动时扫描 `skills/` 并将其转化为 LangGraph 可用的 Tool。
- **Docker 沙箱执行**：所有的 Shell 命令（如 `ls`, `grep`, `python`）均在后端拉起的临时 Docker 容器中执行，确保主机安全。
- **系统工具集成**：提供基础的文件读写、网页内容抓取、搜索等工具。

### 3. 可视化交互画布 (Live Canvas / Artifacts)
- **实时渲染**：前端 Vue 3 实现一个侧边画布组件，用于渲染非文本内容。
- **组件支持**：基于 ECharts 的**数据图表**、实时 **HTML 预览**、以及用于多步任务的**交互式表单**。
- **A2UI 交互**：允许 AI 生成 JSON 定义的 UI 组件，用户可直接在画布上操作并反馈给 AI。

### 4. 自动化与调度 (Automation & Scheduling)
- **定时任务 (Cron)**：支持在配置中或通过对话设定定时触发的消息任务（如：早报、数据定时监控）。
- **外部事件 (Webhooks)**：支持通过 HTTP Endpoint 接收外部推送并触发对应的 Agent 逻辑。

## 非功能需求 (Non-Functional Requirements)
- **安全性**：沙箱环境必须与主机网络隔离，限制 CPU 和内存使用。
- **响应速度**：多渠道分发延迟需控制在 500ms 以内。
- **可扩展性**：新频道的添加应只需实现 `BaseAdapter` 接口。

## 验收标准 (Acceptance Criteria)
- [ ] AI 能够识别并运行根目录 `skills/` 下新定义的自定义 Markdown 技能。
- [ ] Shell 命令执行返回结果且不会对宿主机文件系统造成非授权修改。
- [ ] 能够通过 Telegram 发送消息并收到 JARVIS 的流式回复。
- [ ] 前端画布能成功渲染 AI 生成的测试 HTML 和柱状图。
- [ ] Cron 任务按预期时间点触发消息。

## 超出范围 (Out of Scope)
- 视频/音频实时通话（仅支持语音消息转换）。
- 复杂的企业级工作流引擎集成（仅支持轻量化自动化）。
