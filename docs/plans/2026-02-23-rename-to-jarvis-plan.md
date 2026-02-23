# Rename agents → JARVIS Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将项目所有文档和配置中的旧名称 `agents` 统一替换为 `JARVIS` / `Jarvis` / `jarvis`。

**Architecture:** 逐文件替换，无代码逻辑改动，仅文本内容更新。5 个文件，1 次提交。

**Tech Stack:** 无特殊依赖，直接编辑文件。

---

### Task 1: 更新 README.md 标题

**Files:**
- Modify: `README.md`

**Step 1: 修改标题**

将第 1 行：
```
# Agents Project
```
改为：
```
# JARVIS
```

**Step 2: 确认改动**

打开文件确认第 1 行为 `# JARVIS`，其余内容不变。

---

### Task 2: 更新 pyproject.toml 项目名

**Files:**
- Modify: `pyproject.toml`

**Step 1: 修改 name 字段**

将：
```toml
name = "agents"
```
改为：
```toml
name = "jarvis"
```

**Step 2: 确认改动**

确认 `name = "jarvis"`，其余字段不变。

---

### Task 3: 更新 .devcontainer/README.md

**Files:**
- Modify: `.devcontainer/README.md`

**Step 1: 替换 Docker 镜像名**

将所有 `agents-dev` 替换为 `jarvis-dev`（共出现 2 处）。

**Step 2: 确认改动**

确认文件中不再含有 `agents-dev`。

---

### Task 4: 更新 .devcontainer/QUICK_START.md

**Files:**
- Modify: `.devcontainer/QUICK_START.md`

**Step 1: 替换路径**

将：
```
code /Users/hyh/code/agents
```
改为：
```
code /Users/hyh/code/JARVIS
```

将：
```
cd /Users/hyh/code/agents
```
改为：
```
cd /Users/hyh/code/JARVIS
```

**Step 2: 替换 Docker 镜像名**

将所有 `agents-dev` 替换为 `jarvis-dev`（共出现 4 处）。

**Step 3: 确认改动**

确认文件中不再含有 `agents` 旧路径和 `agents-dev`。

---

### Task 5: 更新 GEMINI.md

**Files:**
- Modify: `GEMINI.md`

**Step 1: 替换正文引用**

将：
```
`agents` monorepo
```
改为：
```
`JARVIS` monorepo
```

将目录结构中：
```
agents/
```
改为：
```
JARVIS/
```

**Step 2: 确认改动**

确认文件中旧名称 `agents`（作为项目名引用）已全部替换，数据库连接串等无关内容不变。

---

### Task 6: 提交所有改动

**Step 1: 暂存文件**

```bash
git add README.md pyproject.toml .devcontainer/README.md .devcontainer/QUICK_START.md GEMINI.md docs/plans/2026-02-23-rename-to-jarvis-design.md docs/plans/2026-02-23-rename-to-jarvis-plan.md
```

**Step 2: 提交**

```bash
git commit -m "docs: rename project from agents to JARVIS across all documentation"
```

**Step 3: 验证**

```bash
git show --stat HEAD
```
Expected: 看到上述 7 个文件已提交。
