# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

这是一个使用 `uv` 作为包管理器的 Python 项目。项目目前处于最小化状态，没有生产依赖，仅配置了开发工具链。

**当前状态**: 这是一个新初始化的项目，`main.py` 文件为空。尚未添加任何应用程序逻辑、测试或生产依赖。

## 开发环境

- **Python 版本**: 3.13（在 `.python-version` 中指定）
- **包管理器**: `uv`（锁文件: `uv.lock`）
- **虚拟环境**: `.venv`（git忽略，由 uv 自动管理）

## 常用开发任务

### 依赖管理
- 安装依赖: `uv sync`
- 添加生产依赖: `uv add <包名>`
- 添加开发依赖: `uv add --group dev <包名>`
- 更新依赖: `uv sync --upgrade`

### 代码质量
- 类型检查 (Pyright): `pyright`
- 代码检查 (Ruff): `ruff check`
- 代码格式化 (Ruff): `ruff format`
- 自动修复检查问题: `ruff check --fix`

### 测试
- 运行测试 (Ty): `ty`
- 运行特定测试: `ty <测试模块>::<测试函数>`（例如: `ty test_main::test_example`）

### 构建
- 构建包: `uv build`
- 清理构建产物: `rm -rf build/ dist/ *.egg-info`

## 项目结构

项目目前采用最小化结构:
- `pyproject.toml` – 项目配置和依赖
- `uv.lock` – 锁定的依赖版本
- `main.py` – 入口点（当前为空）
- `.python-version` – Python 版本指定文件
- `.gitignore` – 标准 Python 忽略规则

## 工具配置

- **Pyright**: 类型检查，通过 `pyproject.toml` 配置（无独立配置文件）
- **Ruff**: 代码检查和格式化，使用默认配置
- **Ty**: 测试运行器，使用默认配置

## 开始开发

要在此项目上开始开发：

1. **添加第一个依赖**: `uv add <包名>`
2. **创建应用程序代码** 在 `main.py` 中或创建适当的包结构
3. **添加测试**: 按照 Python 测试约定创建测试文件
4. **运行质量检查**: `ruff check` 和 `pyright` 确保代码质量

## 未来开发注意事项

- 本项目使用现代 Python 工具链 (uv, ruff, pyright, ty)
- 开发依赖位于 `dev` 依赖组中
- 当前未指定任何生产依赖
- 虚拟环境由 uv 管理，位于 `.venv/`
- 添加大量代码时，考虑创建适当的包结构（例如 `src/agents/`）
