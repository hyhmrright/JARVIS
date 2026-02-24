[中文](README.md) | [English](docs/i18n/readme/README.en.md) | [日本語](docs/i18n/readme/README.ja.md) | [한국어](docs/i18n/readme/README.ko.md) | [Français](docs/i18n/readme/README.fr.md) | [Deutsch](docs/i18n/readme/README.de.md)

# Dev Container 使用指南

## 什么是 Dev Container？

Dev Container 是一个标准化的开发环境配置，使用 Docker 容器来提供一致的开发体验。无论在什么机器上，都能获得相同的开发环境。

## 功能特性

✅ **预配置的 Python 3.13 环境**
✅ **自动安装 uv 包管理器**
✅ **预装 Bun 运行时**（前端开发）
✅ **预装开发工具** (Ruff, Pyright, Pre-commit)
✅ **VS Code 扩展自动安装**
✅ **自动运行 `uv sync`、`pre-commit install` 和 `bun install`**
✅ **代码格式化和 Linting 已配置**

## 如何使用

### 方法一：VS Code (推荐)

1. **安装必需软件**:
   - 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop)
   - 安装 [VS Code](https://code.visualstudio.com/)
   - 安装 VS Code 扩展: `Dev Containers` (ms-vscode-remote.remote-containers)

2. **打开项目**:
   - 在 VS Code 中打开此项目文件夹
   - VS Code 会检测到 `.devcontainer` 配置
   - 点击右下角弹出的 "Reopen in Container" 按钮
   - 或者按 `F1` → 输入 "Dev Containers: Reopen in Container"

3. **等待构建**:
   - 首次打开会构建 Docker 镜像(约 2-5 分钟)
   - 后续打开会很快(10-20 秒)

4. **开始开发**:
   - 所有依赖已自动安装
   - 代码质量工具已配置好
   - 可以直接运行 `python main.py`

### 方法二：命令行

```bash
# 构建容器
docker build -t jarvis-dev -f .devcontainer/Dockerfile .

# 运行容器
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  jarvis-dev bash

# 在容器内
uv sync
python main.py
```
