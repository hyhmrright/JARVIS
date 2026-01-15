# Agents Project

A simple agent system built with LangGraph demonstrating basic agent workflows.

## Overview

This project provides a minimal implementation of an agent system using LangGraph. It demonstrates:

- Creating a StateGraph with message handling
- Defining agent nodes and edges
- Using proper LangChain message types
- Running agent workflows

## Installation

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
