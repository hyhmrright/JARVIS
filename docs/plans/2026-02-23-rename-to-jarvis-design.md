# 设计文档：将项目名称从 agents 更新为 JARVIS

**日期**: 2026-02-23
**状态**: 已批准

## 背景

仓库目录已从 `agents` 改名为 `JARVIS`，但项目内的文档和配置文件仍使用旧名称，需要统一更新。

## 命名规则

| 场景 | 写法 |
|------|------|
| 标题、品牌名 | `JARVIS` |
| 句子中自然叙述 | `Jarvis` |
| pyproject.toml `name` 字段 | `jarvis` |
| Docker 镜像名 | `jarvis-dev` |

## 涉及文件

| 文件 | 改动内容 |
|------|---------|
| `README.md` | 标题 `# Agents Project` → `# JARVIS` |
| `pyproject.toml` | `name = "agents"` → `name = "jarvis"` |
| `.devcontainer/README.md` | `agents-dev` → `jarvis-dev` |
| `.devcontainer/QUICK_START.md` | 路径和镜像名更新 |
| `GEMINI.md` | `agents monorepo` / `agents/` 目录引用更新 |

## 不涉及范围

- `.claude/worktrees/` 临时工作树文件
- `docs/plans/` 历史设计文档
- `node_modules/`、`.venv/` 等依赖目录
