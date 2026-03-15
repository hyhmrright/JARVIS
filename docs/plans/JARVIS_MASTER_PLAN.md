# JARVIS 终极演进规划 (Master Plan: Project Phoenix)

> **目标**: 将 JARVIS 从“可用”提升至全球火爆产品（如 Cursor, Dify, v0）的“极致”标准。

## 核心演进逻辑
**可观测性基石 $\rightarrow$ 智能引擎突破 $\rightarrow$ 颠覆性交互**

如果不先建立 Tracing 和 Evaluation，复杂的 Agent 和 RAG 优化将沦为盲人摸象。因此，必须严格遵循以下顺序推进：

---

## Phase 1: 穿透黑盒 (Observability & Evaluation)
**为什么优先？** 在增加 Hybrid Search 或 Self-Reflection 之前，必须能精确测量“改动到底有没有变好”。

*   **P1.1 全链路追踪 (Tracing)**:
    *   **实现**: 引入 OpenTelemetry 或全面深化 LangSmith 集成。追踪每一次 LLM 调用、工具执行耗时、Token 消耗，以及 Agent 路由决策树。
*   **P1.2 自动化评测 (Eval Suite)**:
    *   **实现**: 建立基准测试集（Benchmarking）。每次 Agent 逻辑变更，自动运行 100+ 个用例（如 RAG 回答准确率、工具选择正确率），输出可视化对比报告。

---

## Phase 2: 智能跃迁 (RAG & Agent Deepening)
**目标:** 让 JARVIS 的回答从“有逻辑”变成“有深度、有记忆、且极其精准”。

*   **P2.1 混合检索引擎 (Hybrid Search + Rerank)**:
    *   **实现**: 在 Qdrant 的基础上，引入 BM25（如 Elasticsearch/Meilisearch 词法检索）进行多路召回，最后通过 Cross-Encoder 模型（如 bge-reranker）进行重排序，彻底解决“找不准”的问题。
*   **P2.2 认知架构升级 (LT/ST Memory & Reflection)**:
    *   **实现**:
        *   **长短期记忆 (LT/ST)**: 引入独立的 Vector Memory 节点，Agent 可以主动 `save_memory()` 和 `search_memory()`，实现跨会话的持续学习。
        *   **自我纠错 (Self-Correction)**: 在 LangGraph 中加入 Review 节点。在关键任务输出前，让 Critic Agent 审查并退回修改，实现“三思而后行”。

---

## Phase 3: 交互革命 (The Canvas Experience)
**目标:** 打破传统的“聊天框”限制，引入当前最前沿的“协作式 UI”。

*   **P3.1 协作画布 (Artifacts / Canvas)**:
    *   **实现**: 参考 Claude Artifacts 或 OpenAI Canvas。当 Agent 生成代码、UI 或长文档时，右侧自动展开独立渲染区。支持版本对比、局部重写（"在此处修改"）和实时预览。
*   **P3.2 深度流式解析 (Deep Streaming UI)**:
    *   **实现**: 前端解析更细粒度的 SSE 事件（不仅是文本，包括思考过程、工具调用进度条、RAG 引用溯源的高亮显示），提供极度丝滑的反馈。

---

## 执行纪律 (Execution Disciplines)
每个子任务必须严格遵循：
1. **Spec 先行**: 使用 `brainstorming` 敲定架构和接口。
2. **TDD 驱动**: 先写 Eval / Test 用例，再写实现。
3. **独立分支**: 使用 Git Worktrees 隔离开发。
