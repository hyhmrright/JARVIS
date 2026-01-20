# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

这是一个使用 LangGraph 构建的 agent 系统演示项目,展示了基本的 agent 工作流程。项目使用 `uv` 作为包管理器,采用现代 Python 工具链。

## 核心架构

项目基于 **LangGraph** 框架构建状态图(StateGraph)来实现 agent 逻辑:

- **StateGraph**: 使用 `MessagesState` 作为状态类型,维护消息历史
- **节点(Nodes)**: 定义 agent 的处理单元(如 `mock_llm` 函数)
- **边(Edges)**: 连接节点定义工作流(START → mock_llm → END)
- **消息类型**: 使用 LangChain 的 `HumanMessage` 和 `AIMessage` 处理对话

当前实现是一个最小化演示,使用 mock LLM 节点返回固定响应。扩展时应保持这种图结构模式。

## 开发环境

- **Python 版本**: 3.13(`.python-version`)
- **包管理器**: `uv`
- **虚拟环境**: `.venv`(自动管理)

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

Pre-commit 会自动执行:
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

- **Ruff**: line-length=88, target-version="py313", quote-style="double"
- **Pyright**: typeCheckingMode="basic"
- **Pre-commit**: 运行 uv-lock、ruff-check、ruff-format 和标准文件检查

## 扩展 Agent 系统

在 `create_agent_graph()` 中添加新节点和边来扩展功能:
1. 定义节点函数,接收和返回 `MessagesState`
2. 使用 `graph.add_node()` 注册节点
3. 使用 `graph.add_edge()` 或 `graph.add_conditional_edges()` 定义流程
4. 使用 `cast()` 确保类型安全

集成真实 LLM 时,将 `mock_llm` 替换为实际的 LangChain LLM 调用,保持相同的函数签名。
