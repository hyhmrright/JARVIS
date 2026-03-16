# 设计规范：调度系统重构 (从 Cron 到间隔调度)

## 1. 背景与目标
目前的调度系统要求用户输入标准的 Cron 表达式（如 `*/30 * * * *`），这对非技术用户极不友好。本项目的目标是彻底简化用户界面，提供直观的“间隔（Interval）”设置方式，即“每隔 X 秒/分/时/天运行一次”。

## 2. 交互设计 (UX)
### 2.1 简单模式 (默认)
- **执行频率**：`每隔 [ 数字输入 ] [ 单位下拉菜单 (秒/分/时/天) ] 运行一次`。
- **首次运行**：默认“立即开始”。
- **预览**：下方实时显示“预计下次运行：YYYY-MM-DD HH:mm:ss”。

### 2.2 进阶设置 (可选)
- **指定起始时间**：如果用户不希望立即开始，可以选择一个未来的时间点作为首次运行时间。后续运行将以此为基准按间隔递增。

## 3. 技术方案 (Technical Strategy)

### 3.1 后端 (Python/APScheduler)
- **存储协议**：为了兼容现有的 `CronJob.schedule` (String 100) 字段且不进行数据库迁移，我们将采用新的前缀协议：
  - `@every 30s` -> 每 30 秒
  - `@every 5m` -> 每 5 分钟
  - `@every 2h` -> 每 2 小时
  - `@every 1d` -> 每 1 天
- **解析引擎** (`backend/app/scheduler/runner.py`):
  ```python
  def parse_schedule(schedule_str: str):
      if schedule_str.startswith("@every "):
          # 解析间隔并返回 IntervalTrigger
          ...
      else:
          # 返回 CronTrigger (保留底层兼容)
          ...
  ```
- **字段扩展**：
  - `CronJob` 模型已有的 `trigger_metadata` 可用于存储 `start_date`。

### 3.2 前端 (Vue 3/TypeScript)
- **组件开发**：在 `ProactivePage.vue` 中重构表单逻辑。
- **状态转换**：
  - UI 上的 `(value: 30, unit: 'minutes')` -> 提交给后端的 `@every 30m`。
  - 获取数据时 `@every 30m` -> 还原回 UI 的 `(value: 30, unit: 'minutes')`。

## 4. 验证计划
- **单元测试**：验证 `parse_schedule` 能够正确解析不同的单位并生成对应的 `IntervalTrigger`。
- **集成测试**：创建一个 10 秒间隔的任务，验证其是否在 10 秒后触发并在数据库中更新 `last_run_at`。
- **UI 测试**：使用 Chrome DevTools 验证下拉菜单切换和数值变动是否正确反映在预览时间中。
