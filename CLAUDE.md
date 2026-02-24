# CLAUDE.md

本文件为 Claude Code 在此代码库中工作时提供指导。

## 分支策略

- **main**：仅用于发版，不得直接提交或开发。只接受来自 dev 等开发分支的 merge。
- **dev**：主开发分支，所有日常开发、bugfix、功能开发均在此分支或其子分支进行。
- 开发完成后：dev → merge → main → push，不得跳过。

## 项目概述

JARVIS 是具备 RAG 知识库、多 LLM 支持、流式对话的 AI 助手平台，采用 monorepo 结构。

## 核心架构

- **backend/**：FastAPI + LangGraph + SQLAlchemy（PostgreSQL）+ Qdrant（向量库）+ MinIO（文件）+ Redis
- **frontend/**：Vue 3 + TypeScript + Vite + Pinia
- **根目录 pyproject.toml**：仅管理开发工具（ruff、pyright、pre-commit），无运行时依赖
- **LLM**：支持 DeepSeek / OpenAI / Anthropic，通过 LangGraph StateGraph 驱动

## 开发环境

- **Python 版本**：3.13（`.python-version`）
- **包管理器**：`uv`
- **虚拟环境**：`.venv`（自动管理）

## 常用命令

### 环境设置
```bash
uv sync                      # 安装所有依赖
```

### 运行应用
```bash
# 后端（在 backend/ 目录）
uv run uvicorn app.main:app --reload

# 前端（在 frontend/ 目录）
bun run dev

# 全栈（根目录）
docker-compose up -d
```

### 代码质量检查
```bash
ruff check                   # 代码检查
ruff check --fix             # 自动修复问题
ruff format                  # 代码格式化
pyright                      # 类型检查
```

### 测试
```bash
# 在 backend/ 目录执行
uv run pytest tests/ -v                        # 运行所有测试
uv run pytest tests/api/test_auth.py -v        # 运行特定测试文件
```

### Pre-commit Hooks
```bash
pre-commit install           # 安装 git hooks
pre-commit run --all-files   # 手动运行所有 hooks
```

Pre-commit 自动执行：
- YAML/TOML/JSON 格式检查
- uv.lock 同步检查
- Ruff lint 和 format
- 文件尾空行和尾随空格检查

### 依赖管理
```bash
uv add <包名>                # 添加生产依赖
uv add --group dev <包名>    # 添加开发依赖
uv sync --upgrade            # 更新依赖
uv lock                      # 手动编辑 pyproject.toml 后重新生成 uv.lock
```

## 工具配置

- **Ruff**：line-length=88, target-version="py313", quote-style="double"
- **Pyright**：typeCheckingMode="basic"
- **Pre-commit**：运行 uv-lock、ruff-check、ruff-format 和标准文件检查

---

# 全局开发规则

## Git 操作前自检

**每次执行 `git commit`、`git push` 或调用 commit/push skill 之前，必须自检：**

```
本 session 是否修改过文件？
   → 是 → 质量循环（simplifier → commit → review）是否已完整通过？
           → 否 → 【STOP】立刻执行质量循环
           → 是 → 继续 git 操作
   → 否 → 工作区是否有未提交改动？（git diff / git diff --cached / git stash list）
           → 有（含 stash）→ 【STOP】必须先完整执行质量循环
           → 无 → 继续 git 操作
```

---

## 代码改动强制流程

### 工具说明

| 工具 | 类型 | 调用方式 | 运行时机 |
|------|------|---------|---------|
| code-simplifier | Task agent | `Task` 工具，`subagent_type: "code-simplifier:code-simplifier"` | commit 之前 |
| pre-push 代码审查 | Skill | `Skill: superpowers:requesting-code-review` | commit 之后、push 之前 |
| PR 代码审查 | Skill | `Skill: code-review:code-review --comment` | push 之后（需 PR 存在） |

### 触发条件（满足任一即触发）

- 使用 Edit / Write / NotebookEdit 修改了任何文件
- 用户意图将变更持久化到 Git 或推送到远程（含"同步"、"上传"、"发 PR"、"存档"、"ship"等表述）
- 准备调用任何 commit / push 相关 skill

### 执行步骤（顺序固定，不可跳过）

```
写代码 / 修改文件
      ↓
╔══════════════════ 质量循环（重复直到无问题）══════════════════╗
║                                                              ║
║  A. 【必须】Task: code-simplifier                            ║
║     （Task agent，会直接修改文件）                            ║
║          ↓                                                   ║
║  B. git add + commit                                         ║
║     首次进入 → git commit                                    ║
║     修复后重入 → git commit --amend（未 push，保持历史干净）  ║
║          ↓                                                   ║
║  C. 【必须】Skill: superpowers:requesting-code-review        ║
║     （需提供 BASE_SHA=HEAD~1、HEAD_SHA=HEAD）                ║
║          ↓                                                   ║
║     发现问题？                                               ║
║       是 → 修复代码 ─────────────────────────→ 回到步骤 A   ║
║       否 ↓                                                   ║
╚══════════════════════════════════════════════════════════════╝
      ↓
git push（立即执行，不得停留）
      ↓（若存在 GitHub PR）
【必须】Skill: code-review:code-review --comment
```

**关键说明：**
- 质量循环必须完整执行（A→B→C）且 C 无问题才能退出
- 修复后重入循环时用 `--amend`（未 push 前保持单一 commit）
- `--amend` 不是跳过 review 的理由，仍需重新执行 C

---

## 禁止跳过流程的常见借口

以下理由均**不得**作为跳过依据：

| 借口 | 正确做法 |
|------|---------|
| "只是简单的一行改动" | 无论改动大小，必须执行 |
| "用户只说了 commit，没说要 review" | commit 本身就是触发条件 |
| "刚才已经 review 过类似代码" | 每次改动后必须重新执行 |
| "这是测试文件 / 文档，不是核心逻辑" | 只要用 Edit/Write 修改了文件就适用 |
| "需要先 push 再 review" | 必须先 review 再 push |
| "用户在催，先提交" | 流程不因催促而跳过 |
| "这段代码我很熟悉" | 熟悉程度不影响流程要求 |
| "这些改动不是本 session 做的" | 只要有未提交改动，就必须执行 |
| "用户没用'commit'这个词" | 只要意图是提交/推送，就触发 |
| "这是 --amend，不是新 commit" | --amend 同样修改历史，必须执行 |
| "改动在 stash 里，工作区是干净的" | stash 中的改动同样需要完整流程 |
| "用户只说了 commit，没说要 push" | commit 后必须立即 push，无需额外指令 |
| "等会儿再 push" | push 是 commit 的必要后续步骤，不得延迟 |

---

## 强制检查点

**执行 git push 之前**，必须确认质量循环已完整通过：

| 步骤 | 完成标志 |
|------|---------|
| A. code-simplifier | Task agent 已运行，文件已整理 |
| B. git add + commit/amend | 所有改动（含 simplifier 修改）已提交 |
| C. requesting-code-review | review 无问题，或所有问题已在下一圈修复 |

以下工具调用前必须确认循环已完成：

- `Bash` 执行 `git push`
- `Skill` 调用 `commit-commands:*`
- `Skill` 调用 `pr-review-toolkit:*`（创建 PR）

**推送后**，若存在 PR，还需执行：
- `Skill` 调用 `code-review:code-review --comment`

**此规则适用于所有项目，无一例外。**
