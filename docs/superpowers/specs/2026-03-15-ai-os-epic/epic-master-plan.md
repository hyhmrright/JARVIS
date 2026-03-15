# JARVIS AI OS Epic: 演进架构与全功能蓝图

## 背景
JARVIS 目前是一个底座非常扎实的多渠道、沙盒化 AI 助手平台。为了使其达到并超越当前市场上最火爆的开源项目（如 Dify、LobeChat、OpenWebUI），我们需要进行一次全面的功能升级（Epic），将其打造成一个完整的企业级 AI 操作系统（AI OS）。

## 核心目标
1.  **对标 LobeChat**: 提供极致的 C 端交互体验（多模态、对话分支、技能商店）。
2.  **对标 OpenWebUI**: 提供强大的协作和极客体验（对话分享、本地模型无缝切换）。
3.  **对标 Dify**: 提供专业级的 AI 业务流编排能力（可视化工作流、LLMOps 看板）。

## 演进策略 (The Master Plan)
鉴于这是一个包含大量前后端及架构重构的超级特性集合（Epic），为保证系统的稳定性和每个特性的高质量交付，我将采用**自下而上、由浅入深、增量交付**的策略。

所有功能按依赖关系和交付价值，严格划分为三个阶段（Phases）。**每个 Phase 将作为独立的 Track 进行开发、测试、提交和 CI 验证。**

---

### Phase 1: 视觉与交互增强 (The Foundation of UX)
**优先级：最高**。这是因为这些功能最能直观提升用户感知，且对现有后端核心逻辑改动较小。

*   **Track 1.1: 视觉多模态 (Vision Integration)**
    *   **后端**: 扩展 `agent/llm.py`，支持接收和传递 Base64 图像数据或图像 URL 至支持 Vision 的模型（GPT-4o, Claude-3.5-Sonnet 等）。处理图片存储（MinIO 临时桶）。
    *   **前端**: 在聊天输入框实现图片拖拽、粘贴上传、预览组件。将图片数据随消息发送至后端。
*   **Track 1.2: 对话分支与历史编辑 (Branching & Editing)**
    *   **数据库**: 修改 `messages` 表结构（增加 `parent_id` 形成树状结构），替代现有的线性列表。
    *   **后端**: API 支持基于特定消息 ID 的分叉（fork）和重新生成。
    *   **前端**: 渲染树状对话流，提供历史消息编辑按钮，实现不同分支的切换。
*   **Track 1.3: 对话快照与公共分享 (Public Sharing)**
    *   **数据库/后端**: 增加 `shared_conversations` 表，生成唯一个只读访问 Token/URL，提供无需鉴权的查询 API。
    *   **前端**: 增加分享按钮；设计一个独立的、移除所有输入框的只读会话渲染页面（含 Canvas 状态快照）。

### Phase 2: 生态与集市 (The Skill Ecosystem)
**优先级：中**。在具备了优秀的交互后，通过商店引入外部能力。

*   **Track 2.1: 技能集市架构 (Skill Market Infrastructure)**
    *   **后端**: 创建 `SkillRegistry` 模块，从配置的外部仓库（如 GitHub 上的 JSON 列表）定期拉取可用的插件元数据。提供安装、卸载、更新 API。
    *   **后端/沙盒**: 支持动态下载 `SKILL.md`，并在沙盒环境中实现热加载而无需重启服务。
*   **Track 2.2: 技能商店前端 (Skill Market UI)**
    *   **前端**: 设计 `SkillStore` 页面，展示技能卡片、标签、搜索。实现一键安装交互和已安装技能管理。
*   **Track 2.3: 预设角色 (Personas) 管理**
    *   **后端/前端**: 允许用户基于系统提示词创建自定义 Agent 角色，并可在工作空间内共享。类似迷你版的技能，但仅修改 Prompt。

### Phase 3: 工作流与可观测性 (The Enterprise Tier)
**优先级：低**。这是最复杂的平台级功能，需要在前两个阶段稳定后进行。

*   **Track 3.1: 可视化工作流引擎前端 (Workflow Studio)**
    *   **前端**: 引入 `VueFlow`。开发 LLM 节点、工具节点、条件节点、API 请求节点的 UI 组件。实现节点拖拽、连线、属性配置。
    *   **前端**: 生成并导出标准的 JSON DSL 格式。
*   **Track 3.2: 动态图编译器 (LangGraph Compiler)**
    *   **后端核心**: 这是整个项目最大的技术挑战。在 `backend/app/agent/` 目录下编写一个解析器，读取前端的 JSON DSL，动态构建并返回可执行的 `LangGraph StateGraph` 对象。
*   **Track 3.3: LLMOps 数据洞察 (LLMOps Dashboard)**
    *   **后端**: 增强 Prometheus 指标导出和 Postgres 日志聚合，提供统计 API。
    *   **前端**: 为 Workspace 管理员开发仪表盘页面，使用 ECharts 展示 Token 消耗、活跃度、工具调用成功率等。

---

## 质量保证与提交流程 (Quality & Delivery Protocol)
在执行上述任何一个 Track 时，我将严格遵守以下约束：

1.  **TDD (测试驱动开发)**: 必须先写或更新测试用例，再实现功能。
2.  **强制本地校验**: 每次代码修改必须通过 `uv run ruff check --fix`, `uv run mypy app` (后端) 和 `bun run lint`, `bun run type-check` (前端)。
3.  **独立提交 (Atomic Commits)**: 每个逻辑单元完成即 commit，提交信息符合规范。
4.  **CI 闭环管理**:
    *   随时决定 push 代码的时机。
    *   Push 后，使用 `gh run list` 和 `gh run view` 监控 GitHub Actions 状态。
    *   如果 CI 失败，必须主动分析日志并在当前分支修复，直到 CI 绿灯。
5.  **不中断现有服务**: 所有的功能增强必须保证旧有 API 的向后兼容性。

## 下一步行动
我们将从 **Phase 1 -> Track 1.1: 视觉多模态 (Vision Integration)** 开始实施。