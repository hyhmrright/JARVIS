# 调度系统重构实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将复杂的 Cron 表达式输入替换为直观的“每隔 X 秒/分/时/天”间隔设置，并保持后端兼容性。

**Architecture:** 采用“前缀解析协议”（@every），前端负责将 UI 状态转换为协议字符串，后端负责解析并映射到 `APScheduler` 的 `IntervalTrigger`。

**Tech Stack:** Python (FastAPI, APScheduler), Vue 3 (TypeScript), Tailwind CSS.

---

## Chunk 1: 后端解析逻辑重构

**Files:**
- Modify: `backend/app/scheduler/runner.py`
- Create: `backend/tests/scheduler/test_runner_v2.py`

- [ ] **Step 1: 编写解析逻辑的测试用例**
验证 `@every 30s`, `@every 5m`, `@every 2h`, `@every 1d` 以及标准 Cron 格式的解析。

- [ ] **Step 2: 在 `runner.py` 中实现 `parse_trigger` 并重构 `register_cron_job`**
实现基于正则表达式的解析引擎。

- [ ] **Step 3: 运行后端测试并验证成功**

- [ ] **Step 4: 提交后端变更**

---

## Chunk 2: 前端 UI 重构

**Files:**
- Modify: `frontend/src/pages/ProactivePage.vue`

- [ ] **Step 1: 修改数据转换逻辑**
实现 UI 状态与 `@every` 协议字符串的互转。

- [ ] **Step 2: 替换 Cron 输入框为 Interval Selector**
构建符合视觉设计的组合输入组件。

- [ ] **Step 3: 实现“下次运行时间”实时预览**

- [ ] **Step 4: 提交前端变更**

---

## Chunk 3: 验证与交付

- [ ] **Step 1: 端到端功能测试**
创建一个 10s 间隔的任务，验证触发流程。

- [ ] **Step 2: 运行全量 Lint 和类型检查**

- [ ] **Step 3: 最终确认并完成**
