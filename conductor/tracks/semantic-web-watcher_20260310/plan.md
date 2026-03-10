# Implementation Plan: Semantic Web Watcher Monitoring

## Phase 1: 基础设施与数据模型扩展
*本阶段重点是扩展 `CronJob` 模型，以支持语义监控所需的元数据，并准备测试环境。*

- [ ] Task: 扩展 `CronJob` 模型与迁移
    - [ ] 在 `app/db/models.py` 的 `CronJob` 中确认/添加 `trigger_metadata` 对 `last_semantic_summary` 的支持。
    - [ ] 创建并运行 Alembic 迁移脚本（如需字段调整）。
- [ ] Task: TDD 环境准备
    - [ ] 创建 `tests/scheduler/test_semantic_watcher.py`。
    - [ ] 编写模拟 LLM 对比逻辑的失败测试用例。
- [ ] Task: Conductor - User Manual Verification 'Phase 1: 基础设施与数据模型扩展' (Protocol in workflow.md)

## Phase 2: 语义触发器逻辑实现 (TDD)
*本阶段实现核心的 `SemanticWatcherProcessor`，集成 LLM 对比逻辑。*

- [ ] Task: 实现 `SemanticWatcherProcessor` (Red Phase)
    - [ ] 在 `tests/scheduler/test_semantic_watcher.py` 中编写针对 `should_fire` 的单元测试。
    - [ ] 模拟网页变动但语义未变的情况（预期返回 `False`）。
    - [ ] 模拟语义重大变动的情况（预期返回 `True`）。
- [ ] Task: 实现 `SemanticWatcherProcessor` (Green Phase)
    - [ ] 在 `app/scheduler/triggers.py` 中新增 `SemanticWatcherProcessor` 类。
    - [ ] 实现基于 LLM 的文本对比逻辑。
    - [ ] 确保测试通过。
- [ ] Task: 优化与重构 (Refactor Phase)
    - [ ] 提取 LLM 对比提示词（Prompt）到独立模块。
    - [ ] 处理超长文本的分片与摘要逻辑。
- [ ] Task: Conductor - User Manual Verification 'Phase 2: 语义触发器逻辑实现 (TDD)' (Protocol in workflow.md)

## Phase 3: 工具接口与 Agent 集成
*将语义监控能力开放给 Agent，使其能通过工具设置此类任务。*

- [ ] Task: 升级 `cron_set` 工具
    - [ ] 修改 `app/tools/cron_tool.py`，允许传入 `trigger_type="semantic_watcher"`。
    - [ ] 支持传入初始监控 URL 和语义监控目标（Target）。
- [ ] Task: 集成测试
    - [ ] 编写端到端测试，验证 Agent 调用工具后，后台能正确触发语义监控。
- [ ] Task: Conductor - User Manual Verification 'Phase 3: 工具接口与 Agent 集成' (Protocol in workflow.md)
