# JARVIS 多人协作开发基础设施 - 设计文档

## 目标

为 JARVIS 项目建立完整的开源协作基础设施，包括：许可证、贡献指南、Issue/PR 模板、CI 流水线、自动标签、依赖更新、worktree 开发规则。所有协作文件采用中英双语。

## 决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 许可证 | MIT | 最宽松，最易吸引贡献者 |
| 协作文件语言 | 中英双语 | 覆盖面最广 |
| GitHub 默认分支 | 改为 dev | 贡献者 fork 后默认在 dev 上工作 |
| 规则存放位置 | CLAUDE.md + CONTRIBUTING.md | AI 助手规则和人类开发者规则互补 |

## 文件清单

| 文件 | 动作 |
|------|------|
| `LICENSE` | 新建 - MIT |
| `CODE_OF_CONDUCT.md` | 新建 - Contributor Covenant v2.1 中英双语 |
| `SECURITY.md` | 新建 - 漏洞报告政策中英双语 |
| `.github/CONTRIBUTING.md` | 新建 - 贡献指南中英双语，含 worktree 工作流 |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | 新建 - Bug 报告 YAML 表单 |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | 新建 - 功能请求 YAML 表单 |
| `.github/ISSUE_TEMPLATE/config.yml` | 新建 - 禁止空白 issue |
| `.github/pull_request_template.md` | 新建 - PR 模板中英双语 |
| `.github/workflows/ci.yml` | 新建 - CI 流水线 |
| `.github/workflows/labeler.yml` | 新建 - 自动标签 workflow |
| `.github/labeler.yml` | 新建 - 标签路径规则 |
| `.github/dependabot.yml` | 新建 - 依赖自动更新 |
| `.gitignore` | 修改 - 添加 `.worktrees/` |
| `CLAUDE.md` | 修改 - 添加协作分支命名和 worktree 规则 |
