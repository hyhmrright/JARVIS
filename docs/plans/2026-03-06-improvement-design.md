# JARVIS Improvement Design — 2026-03-06

## 背景

对项目现状进行全面分析后，发现以下三类改进方向：性能瓶颈、代码质量（重构+测试）、功能缺口。
本设计文档覆盖三个 PR 的完整方案。

---

## 执行顺序

```
立即并行开始
 ├── PR-B: feature/perf-routing      （独立，改 router.py）
 └── PR-A: fix/internal-cleanup      （UX 改善 + 重构 + 测试）
          ↓ PR-A 合并后
      PR-C: feature/ux-improvements  （功能完善，依赖干净的 chat.py）
```

---

## PR-B：性能优化

**分支：** `feature/perf-routing`

### B.1 路由分类改规则优先

**问题：** `classify_task()` 每条消息都发一次额外 LLM 请求，增加 1-2 秒延迟和额外 token 消耗。

**方案：规则层优先，LLM 兜底**

```
用户消息
    ↓
_rule_based_classify()  — 关键词/长度规则（<1ms）
    ├── 命中 → 直接返回分类，跳过 LLM
    └── 未命中 → 调用 LLM 分类（保留现有逻辑）
```

规则示例：
- 消息含"写代码/debug/实现/function/class" → `code`
- 消息含"搜索/查找/调研/research/找一下" → `research`
- 消息含"写文章/翻译/总结/润色" → `writing`
- 消息长度 < 50 字且无明确动作词 → `simple`
- 其余 → LLM 兜底

**预期效果：** 70-80% 消息走规则，0 额外延迟。

**改动文件：**
- `backend/app/agent/router.py` — 新增 `_rule_based_classify()`，在 `classify_task()` 开头调用
- `backend/tests/agent/test_router.py` — 新增规则层测试用例

### B.2 Supervisor 流式体验改善

**问题：** `route == "complex"` 时 `supervisor.ainvoke()` 一次性返回，用户等待期间无任何输出。

**方案：轻量前置 status 事件 + 结果分块 yield**

```python
# 在 ainvoke 前 yield status 事件
yield _format_sse({"type": "status", "message": "正在规划复杂任务..."})
final_state = await supervisor.ainvoke(SupervisorState(messages=lc_messages))
# 结果分块输出（每 50 字一个 delta）
```

**改动文件：**
- `backend/app/api/chat.py` — `route == "complex"` 分支，约 10 行

---

## PR-A：内部清洁

**分支：** `fix/internal-cleanup`

### A.1 改善 Gateway `_run_agent` 错误提示

**现状：** `agent_runner.py` 已有 try/except，异常时返回英文 `"Agent execution failed."`，不够用户友好。

**改进：** 将错误返回改为中文友好提示，并补充测试覆盖异常路径。

```python
except Exception:
    logger.exception("gateway_agent_error")
    return "抱歉，处理请求时出现错误，请稍后重试。"  # 原为英文，改为中文
```

**改动文件：**
- `backend/app/gateway/agent_runner.py`
- `backend/tests/gateway/test_gateway_agent.py` — 新增异常场景测试

### A.2 拆解 `generate()` 函数

**问题：** `chat.py` 的外层 `chat_stream()`（含 RAG 注入、历史加载）和内层 `generate()`（工具加载、图创建、SSE 事件、消息存储）合计 180+ 行，职责过重，测试困难。

**方案：拆成 4 个模块级私有函数**

```
chat_stream()                 ← 只做请求校验、历史加载、RAG 注入
generate()                    ← 只做流程编排，~30 行
    ├── _load_tools()         ← MCP + Plugin tools 加载（从 generate 提取）
    ├── _stream_graph()       ← expert/simple 路由的 SSE 流
    ├── _stream_supervisor()  ← complex 路由的 SSE 流
    └── _save_response()      ← 消息写库 + markdown sync
```

**改动文件：**
- `backend/app/api/chat.py`

### A.3 补全 API 层集成测试

**改动文件：**
- `backend/tests/api/test_chat.py` — 新增（当前不存在，本 PR 新建），覆盖正常流、工具调用流、consent 流、错误处理
- `backend/tests/api/test_conversations.py` — 已存在，扩展创建/列表/删除会话、消息历史加载的测试用例

用 `pytest-asyncio` + `AsyncMock` mock LangGraph graph，不依赖真实 LLM。

---

## PR-C：功能完善

**分支：** `feature/ux-improvements`（依赖 PR-A 合并）

### C.1 对话标题自动生成

**问题：** 所有对话标题固定为 "New Conversation"。

**方案：**

```
AI 回复完成（写入 DB）
    ↓
conv.title == "New Conversation"？
    ├── 是 → asyncio.create_task(_generate_title())  ← 不阻塞
    │         ├── 用 LLM 从消息生成 ≤10 字标题
    │         ├── UPDATE conversations SET title=...
    │         └── yield SSE {"type": "title_updated", "title": "..."}
    └── 否 → 跳过
```

前端监听 `title_updated` 事件实时更新侧边栏，无需刷新。

**改动文件：**
- `backend/app/api/chat.py` — `_save_response()` 中新增标题生成触发
- `backend/app/agent/` — 新增 `title_generator.py`
- `frontend/src/stores/chat.ts` — 处理 `title_updated` SSE 事件

### C.2 多轮对话 RAG 检索

**问题：** `maybe_inject_rag_context()` 只在第一条消息时检索一次，后续轮次忽略。

**改进：**
1. 每轮都检索，用「当前消息 + 最近一条 AI 消息摘要」作为查询
2. 把 score_threshold 过滤从 Python 层移到 Qdrant 查询层（减少网络传输）

```python
# retriever.py
combined_query = f"{query}\n{last_ai_content[:200]}" if last_ai_content else query
hits = await client.search(
    collection_name=...,
    query_vector=query_vec,
    limit=top_k,
    score_threshold=score_threshold,  # 移到 Qdrant 层
)
```

**改动文件：**
- `backend/app/rag/retriever.py`
- `backend/app/api/chat.py` — 传入 `last_ai_content`

### C.3 AgentSession 状态写入

**问题：** `agent_sessions` 表存在但从未真正写入 session 状态。

**方案：** 在 `_save_response()` 中写入 AgentSession 生命周期：

```
generate() 开始   → INSERT agent_sessions (status=active)
正常结束          → UPDATE status=completed, completed_at=now()
异常              → UPDATE status=error
```

为 Admin Panel、用量统计、调试提供真实数据。

**改动文件：**
- `backend/app/api/chat.py` — `_save_response()` 中写入 AgentSession
- `backend/alembic/versions/` — 确认 agent_sessions 迁移已存在（无需新迁移）

---

## 验证清单

每个 PR 合并前必须通过：

```bash
cd backend && uv run ruff check --fix && uv run ruff format
cd backend && uv run mypy app
cd backend && uv run pytest --collect-only -q
cd backend && uv run pytest tests/ -v
cd frontend && bun run lint:fix && bun run type-check
docker compose up -d && docker compose ps
pre-commit run --all-files
```
