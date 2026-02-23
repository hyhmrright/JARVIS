# CLAUDE.md

本文件为 Claude Code 在此代码库中工作时提供指导。

## 分支策略

- **main**：仅用于发版，不得直接提交或开发。只接受来自 dev 等开发分支的 merge。
- **dev**：主开发分支，所有日常开发、bugfix、功能开发均在此分支或其子分支进行。
- 开发完成后：dev → merge → main → push，不得跳过。

## 项目概述

基于 LangGraph 构建的 agent 系统演示项目，展示基本的 agent 工作流程。使用 `uv` 作为包管理器，采用现代 Python 工具链。

## 核心架构

项目基于 **LangGraph** 框架构建状态图（StateGraph）实现 agent 逻辑：

- **StateGraph**：使用 `MessagesState` 作为状态类型，维护消息历史
- **节点（Nodes）**：定义 agent 的处理单元（如 `mock_llm` 函数）
- **边（Edges）**：连接节点定义工作流（START → mock_llm → END）
- **消息类型**：使用 LangChain 的 `HumanMessage` 和 `AIMessage` 处理对话

当前实现为最小化演示，使用 mock LLM 节点返回固定响应。扩展时应保持这种图结构模式。

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
python main.py               # 运行 agent 演示
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
ty                           # 运行所有测试
ty test_main::test_example   # 运行特定测试
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
```

## 工具配置

- **Ruff**：line-length=88, target-version="py313", quote-style="double"
- **Pyright**：typeCheckingMode="basic"
- **Pre-commit**：运行 uv-lock、ruff-check、ruff-format 和标准文件检查

## 扩展 Agent 系统

在 `create_agent_graph()` 中添加新节点和边来扩展功能：
1. 定义节点函数，接收和返回 `MessagesState`
2. 使用 `graph.add_node()` 注册节点
3. 使用 `graph.add_edge()` 或 `graph.add_conditional_edges()` 定义流程
4. 使用 `cast()` 确保类型安全

集成真实 LLM 时，将 `mock_llm` 替换为实际的 LangChain LLM 调用，保持相同的函数签名。

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
