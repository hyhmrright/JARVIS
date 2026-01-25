# Agents Project

A simple agent system built with LangGraph demonstrating basic agent workflows.

## Overview

This project provides a minimal implementation of an agent system using LangGraph. It demonstrates:

- Creating a StateGraph with message handling
- Defining agent nodes and edges
- Using proper LangChain message types
- Running agent workflows

## Installation

### 🐳 Option 1: Dev Container (推荐)

使用 Dev Container 可以获得开箱即用的标准化开发环境，无需在本地安装任何依赖:

1. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop)
2. 安装 [VS Code](https://code.visualstudio.com/) 和 `Dev Containers` 扩展
3. 在 VS Code 中打开此项目
4. 点击右下角的 "Reopen in Container" 或按 `F1` → "Dev Containers: Reopen in Container"
5. 等待容器构建完成(首次约 2-5 分钟)

**优势:**
- ✅ 预配置的 Python 3.13 环境
- ✅ 自动安装所有依赖
- ✅ VS Code 扩展自动配置
- ✅ 开箱即用的代码质量工具

详细说明请查看 [Dev Container 使用指南](.devcontainer/README.md)

### 💻 Option 2: 本地安装

1. Ensure you have Python 3.13+ installed
2. Install [uv](https://github.com/astral-sh/uv) if not already installed
3. Clone this repository
4. Install dependencies:

```bash
uv sync
```

## Usage

Run the agent demonstration:

```bash
python main.py
```

This will execute a simple agent workflow that:
1. Creates a graph with a mock LLM node
2. Processes a user message
3. Returns an AI response

## Project Structure

- `main.py` - Main agent implementation
- `pyproject.toml` - Project configuration and dependencies
- `.pre-commit-config.yaml` - Code quality hooks
- `uv.lock` - Locked dependency versions
- `.devcontainer/` - Dev Container configuration

## Development

### Code Quality

This project uses modern Python tooling:

- **Ruff** for linting and formatting
- **Pyright** for type checking
- **Pre-commit** for automated code quality checks

Run code quality checks:

```bash
# Lint and format
python -m ruff check main.py
python -m ruff format main.py

# Type checking
python -m pyright main.py
```

### Pre-commit Hooks

Install pre-commit hooks:

```bash
pre-commit install
```

The hooks will automatically run on `git commit` to ensure code quality.

## Dependencies

- **langgraph** - Agent graph framework
- **langchain-core** - Core LangChain components

### Development Dependencies

- **ruff** - Code linting and formatting
- **pyright** - Type checking
- **pre-commit** - Git hook management
- **ty** - Test runner

## License

MIT
