# JARVIS 多人协作开发基础设施 - 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 JARVIS 建立完整的开源协作基础设施（许可证、贡献指南、CI、模板、worktree 规则）

**Architecture:** 纯配置/文档任务，无运行时代码改动。所有协作文件放在 `.github/` 目录下，worktree 规则嵌入 CLAUDE.md。中英双语文件采用同一文件内分段展示。

**Tech Stack:** GitHub Actions, YAML, Markdown

---

### Task 1: LICENSE + CODE_OF_CONDUCT + SECURITY

**Files:**
- Create: `LICENSE`
- Create: `CODE_OF_CONDUCT.md`
- Create: `SECURITY.md`

**Step 1: 创建 MIT LICENSE**

标准 MIT 许可证，年份 2026，版权持有人 hyhmrright。

**Step 2: 创建 CODE_OF_CONDUCT.md**

Contributor Covenant v2.1 中英双语版本。

**Step 3: 创建 SECURITY.md**

安全漏洞报告政策，引导使用 GitHub Private Vulnerability Reporting。中英双语。

**Step 4: Commit**

```bash
git add LICENSE CODE_OF_CONDUCT.md SECURITY.md
git commit -m "docs: add MIT license, code of conduct, and security policy"
```

---

### Task 2: Issue 模板 + PR 模板

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Create: `.github/pull_request_template.md`

**Step 1: 创建 bug_report.yml**

YAML 表单格式，字段：版本/描述/复现步骤/期望行为/影响组件（下拉选择）。中英双语标签。

**Step 2: 创建 feature_request.yml**

字段：解决什么问题/方案描述/目标组件（下拉选择）。中英双语标签。

**Step 3: 创建 config.yml**

禁止空白 issue，引导到 GitHub Discussions。

**Step 4: 创建 pull_request_template.md**

PR 模板含 Summary/Related Issue/Type of change/Checklist。中英双语。

**Step 5: Commit**

```bash
git add .github/ISSUE_TEMPLATE/ .github/pull_request_template.md
git commit -m "docs: add issue templates and PR template"
```

---

### Task 3: CI 流水线

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: 创建 ci.yml**

触发条件：push/PR to main/dev。Job 矩阵：
- backend-lint: ruff check + ruff format --check
- backend-type: pyright
- backend-test: pytest（postgres service container）
- frontend-lint: bun run lint
- frontend-type: bun run type-check

**Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions CI pipeline"
```

---

### Task 4: 自动标签 + Dependabot

**Files:**
- Create: `.github/workflows/labeler.yml`
- Create: `.github/labeler.yml`
- Create: `.github/dependabot.yml`

**Step 1: 创建 labeler workflow + 配置**

基于 PR 改动路径自动打标签：
- `backend/**` → `backend`
- `frontend/**` → `frontend`
- `database/**`, `docker-compose.yml` → `infrastructure`
- `docs/**`, `*.md` → `documentation`

**Step 2: 创建 dependabot.yml**

监控 pip (backend)、npm (frontend)、github-actions。

**Step 3: Commit**

```bash
git add .github/workflows/labeler.yml .github/labeler.yml .github/dependabot.yml
git commit -m "ci: add auto-labeler and Dependabot configuration"
```

---

### Task 5: CONTRIBUTING.md（贡献指南）

**Files:**
- Create: `.github/CONTRIBUTING.md`

**Step 1: 创建 CONTRIBUTING.md**

中英双语，内容覆盖：
- 前置条件（Docker, Python 3.13, uv, Bun）
- 本地开发环境搭建步骤
- 分支命名规范：`feature/xxx`, `fix/xxx`, `docs/xxx`, `infra/xxx`
- Commit 消息规范（Conventional Commits）
- PR 提交流程和检查清单
- Worktree 并行开发指南
- 代码风格要求

**Step 2: Commit**

```bash
git add .github/CONTRIBUTING.md
git commit -m "docs: add bilingual contributing guide with worktree workflow"
```

---

### Task 6: 更新 .gitignore + CLAUDE.md

**Files:**
- Modify: `.gitignore` — 添加 `.worktrees/`
- Modify: `CLAUDE.md` — 在「分支策略」后添加协作分支命名和 worktree 规则

**Step 1: .gitignore 添加 worktree 目录**

在 `# Claude Code` 部分后添加 `.worktrees/`。

**Step 2: CLAUDE.md 添加协作规则**

在「分支策略」章节末尾添加：
- 协作分支命名规范
- Worktree 开发规则（命名、端口、环境初始化）
- Worktree 快速参考

**Step 3: Commit**

```bash
git add .gitignore CLAUDE.md
git commit -m "docs: add worktree rules and collaboration branch naming to CLAUDE.md"
```

---

### Task 7: 更改 GitHub 默认分支 + 创建 Labels

**Step 1: 更改默认分支为 dev**

```bash
gh repo edit --default-branch dev
```

**Step 2: 创建标准 Labels**

批量创建：good first issue, help wanted, bug, enhancement, documentation, frontend, backend, rag, infrastructure, breaking change, needs-triage, blocked, duplicate, wontfix

**Step 3: 启用 GitHub Discussions**

```bash
gh repo edit --enable-discussions
```
