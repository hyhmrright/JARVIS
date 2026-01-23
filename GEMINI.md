# Agents 项目上下文

本文档为 Gemini 提供关于 `agents` 项目的上下文信息。

## 项目概览

**目的**: 一个使用 [LangGraph](https://langchain-ai.github.io/langgraph/) 的最小化 Agent 系统演示。
**核心功能**:
*   实现了一个 `StateGraph` 来管理对话状态。
*   使用 `MessagesState` 处理消息历史（`HumanMessage`, `AIMessage`）。
*   演示了一个基本的工作流：`START` -> `mock_llm` -> `END`。
*   当前使用一个返回静态响应的 mock LLM 节点。

## 架构

本项目遵循标准的 LangGraph 架构：
*   **State (状态)**: `MessagesState` (LangGraph 用于消息历史的标准状态)。
*   **Nodes (节点)**: 处理状态的函数 (例如 `main.py` 中的 `mock_llm`)。
*   **Edges (边)**: 定义节点之间的控制流。
*   **Graph (图)**: 编译后的可执行工作流。

## 环境与依赖

*   **语言**: Python 3.13+
*   **包管理器**: `uv`
*   **主要依赖**:
    *   `langgraph`: 编排框架。
    *   `langchain-core`: 消息和链的原语。

## 构建与运行

### 设置
1.  确保已安装 **uv**。
2.  安装依赖：
    ```bash
    uv sync
    ```
    这将创建/更新 `.venv` 虚拟环境。

### 执行
运行主要的 Agent 演示：
```bash
python main.py
```

## 开发工作流

### 代码质量
本项目使用现代 Python 工具强制执行严格的代码质量标准。

*   **Linting (代码检查) & Formatting (格式化)**: [Ruff](https://docs.astral.sh/ruff/)
    ```bash
    # 检查并修复 lint 问题
    uv run ruff check --fix

    # 格式化代码
    uv run ruff format
    ```

*   **类型检查**: [Pyright](https://microsoft.github.io/pyright/)
    ```bash
    uv run pyright
    ```

*   **Pre-commit Hooks (预提交钩子)**:
    项目使用 `pre-commit` 自动执行检查（ruff, uv-lock, 尾随空格等）。
    ```bash
    # 安装钩子
    uv run pre-commit install

    # 手动对所有文件运行
    uv run pre-commit run --all-files
    ```

### 测试
*   **测试运行器**: `ty` (根据 `pyproject.toml` 和 `CLAUDE.md`)。
    ```bash
    uv run ty
    ```

## 关键文件

*   `main.py`: 入口点，包含图定义 (`create_agent_graph`)、mock 节点 (`mock_llm`) 和执行逻辑。
*   `pyproject.toml`: `uv`、依赖项、`ruff` 和 `pyright` 的配置文件。
*   `CLAUDE.md`: 现有的 Claude/Cursor 指令文件，包含详细的工作流信息。
*   `.pre-commit-config.yaml`: Pre-commit 钩子的配置。
