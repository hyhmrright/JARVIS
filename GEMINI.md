# Agents 项目上下文

本文档为 Gemini 提供关于 `agents` 项目的准确上下文信息。

## 项目概览

**目的**: 使用 LangGraph 构建的最小化 Agent 系统，支持 DeepSeek 模型。
**核心功能**:
*   使用 `StateGraph` 管理对话流。
*   状态管理采用 `dataclass` 以确保 Python 3.13 下的类型兼容性。
*   集成 `langchain-deepseek` 访问真实大模型。

## 架构

*   **状态 (State)**: 使用 `AgentState` (`dataclass`)，包含 `messages` 字段，通过 `add_messages` 进行合并。
*   **节点 (Nodes)**:
    *   `agent`: 调用 DeepSeek API 处理对话。
*   **控制流**: `START` -> `agent` -> `END`。
*   **配置**: 自动从系统环境变量 `DEEPSEEK_API_KEY` 读取 API Key。

## 环境与依赖

*   **语言**: Python 3.13.12 (受 uv 管理)
*   **包管理器**: `uv`
*   **核心依赖**:
    *   `langgraph`: 编排框架。
    *   `langchain-core`: 消息原语。
    *   `langchain-deepseek`: DeepSeek 模型支持。
*   **开发依赖**:
    *   `ty`: **首选**类型检查工具。
    *   `ruff`: Lint 检查与代码格式化。
    *   `pre-commit`: 提交前自动检查。

## 开发工作流

### 设置与运行
1.  **安装依赖**:
    ```bash
    uv sync --all-extras
    ```
2.  **安装 Git 钩子**:
    ```bash
    uv run pre-commit install
    ```
3.  **运行程序**:
    ```bash
    uv run main.py
    ```

### 分支策略
*   **main 分支**: 部署分支（稳定版）。
*   **dev 分支**: 开发分支。**所有日常修改必须在此分支进行**。
*   **合并**: 仅在明确指令时将 `dev` 合并至 `main`。

### 自动化规范
*   **修改-提交-推送**: 每次修改后，Agent 会自动执行：
    1.  `uv run ruff check --fix` (Lint 修复)
    2.  `uv run ty` (类型检查)
    3.  `git add . && git commit -m "..." && git push origin dev`

## 技术细节 (Python 3.13 特有)
*   **类型识别**: 在 Python 3.13 中，`StateGraph` 的 schema 必须使用 `dataclass` 或显式 Pydantic 模型，以避免 `TypedDictLikeV1` 协议匹配错误。
*   **导入路径**: `add_messages` 统一从 `langgraph.graph` 导入。
