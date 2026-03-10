# Implementation Plan: Ollama Support Integration

## Phase 1: Backend Infrastructure & Model Discovery
- [x] Task: 配置 Ollama 基础设置 687773f
    - [ ] 在 `backend/app/core/config.py` 中添加 `OLLAMA_BASE_URL` 配置。
- [x] Task: 实现 Ollama 模型发现服务 (TDD) 3d9e090
    - [ ] 编写测试用例 `tests/infra/test_ollama_discovery.py` 模拟 Ollama API 响应。
    - [ ] 在 `backend/app/infra/ollama.py` 中实现模型获取逻辑。
    - [ ] 验证测试通过。
- [x] Task: 集成 ChatOllama 到模型工厂 (TDD) a814288
    - [ ] 编写测试用例 `tests/agent/test_ollama_factory.py`。
    - [ ] 在 `backend/app/agent/factory.py` 中集成 `ChatOllama`。
    - [ ] 验证测试通过。
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Backend Infrastructure & Model Discovery' (Protocol in workflow.md)

## Phase 2: Chat, RAG & Tool Integration
- [ ] Task: 验证流式输出支持 (TDD)
    - [ ] 编写端到端测试 `tests/api/test_ollama_stream.py`。
    - [ ] 确保 `backend/app/api/conversations.py` 能正确处理 Ollama 的流式响应。
    - [ ] 验证测试通过。
- [ ] Task: 集成 RAG 知识库支持 (TDD)
    - [ ] 编写集成测试 `tests/rag/test_ollama_rag.py`。
    - [ ] 确保 Ollama 模型能够接收 RAG 检索到的上下文并进行回复。
    - [ ] 验证测试通过。
- [ ] Task: 验证工具调用能力 (TDD)
    - [ ] 编写测试用例 `tests/agent/test_ollama_tools.py`（使用 Llama 3.1 等支持模型）。
    - [ ] 调整 LangGraph Agent 逻辑以适配 Ollama 的工具调用格式。
    - [ ] 验证测试通过。
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Chat, RAG & Tool Integration' (Protocol in workflow.md)

## Phase 3: Frontend UI & Final Validation
- [ ] Task: 动态加载 Ollama 模型到前端 (TDD)
    - [ ] 编写 Vitest 测试 `frontend/src/tests/ollama_models.test.ts`。
    - [ ] 修改模型选择组件，使其能够合并来自后端的动态 Ollama 模型列表。
    - [ ] 验证测试通过。
- [ ] Task: 整体冒烟测试与 UI 优化
    - [ ] 确保深色奢华 UI 在使用本地模型时响应依然丝滑。
    - [ ] 添加 Ollama 服务连接状态的 UI 提示（可选）。
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Frontend UI & Final Validation' (Protocol in workflow.md)