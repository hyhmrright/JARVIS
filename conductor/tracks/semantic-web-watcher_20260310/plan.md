# Implementation Plan: Semantic Web Watcher Monitoring

## Phase 1: 基础设施与数据模型扩展 [checkpoint: 5646c69]
*本阶段重点是扩展 `CronJob` 模型，以支持语义监控所需的元数据，并准备测试环境。*

- [x] Task: 扩展 `CronJob` 模型与迁移 (已确认: JSONB 字段已支持存储 last_semantic_summary，无需迁移) 5646c69
- [x] Task: TDD 环境准备 (已编写失败测试用例) 5646c69
- [x] Task: Conductor - User Manual Verification 'Phase 1: 基础设施与数据模型扩展' (Protocol in workflow.md) 5646c69

## Phase 2: 语义触发器逻辑实现 (TDD)
*本阶段实现核心的 `SemanticWatcherProcessor`，集成 LLM 对比逻辑。*

- [x] Task: 实现 `SemanticWatcherProcessor` (Red Phase) (已编写并确认失败测试用例) 5646c69
- [x] Task: 实现 `SemanticWatcherProcessor` (Green Phase) (已集成并测试通过) 5646c69
- [x] Task: 优化与重构 (Refactor Phase) (已提取提示词并实现截断逻辑) 5646c69
- [~] Task: Conductor - User Manual Verification 'Phase 2: 语义触发器逻辑实现 (TDD)' (Protocol in workflow.md)

## Phase 3: 工具接口与 Agent 集成
*将语义监控能力开放给 Agent，使其能通过工具设置此类任务。*

- [ ] Task: 升级 `cron_set` 工具
    - [ ] 修改 `app/tools/cron_tool.py`，允许传入 `trigger_type="semantic_watcher"`。
    - [ ] 支持传入初始监控 URL 和语义监控目标（Target）。
- [ ] Task: 集成测试
    - [ ] 编写端到端测试，验证 Agent 调用工具后，后台能正确触发语义监控。
- [ ] Task: Conductor - User Manual Verification 'Phase 3: 工具接口与 Agent 集成' (Protocol in workflow.md)
