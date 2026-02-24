[中文](QUICK_START.md) | [English](docs/i18n/quick-start/QUICK_START.en.md) | [日本語](docs/i18n/quick-start/QUICK_START.ja.md) | [한국어](docs/i18n/quick-start/QUICK_START.ko.md) | [Français](docs/i18n/quick-start/QUICK_START.fr.md) | [Deutsch](docs/i18n/quick-start/QUICK_START.de.md)

# 🚀 Dev Container 快速参考

## 一键启动 (VS Code)

```bash
# 1. 打开 VS Code
code path/to/JARVIS

# 2. 按 F1,输入:
Dev Containers: Reopen in Container

# 3. 等待构建完成,开始编码!
```

---

## 命令行使用

### 构建镜像
```bash
cd path/to/JARVIS
docker build -t jarvis-dev -f .devcontainer/Dockerfile .
```

### 运行程序
```bash
docker run --rm \
  -v $(pwd):/workspace \
  jarvis-dev \
  bash -c "cd /workspace && uv sync && uv run python main.py"
```

### 进入交互式 Shell
```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  jarvis-dev bash
```

---

## 常用命令

### 在容器内
```bash
# 安装依赖
uv sync

# 运行程序
uv run python main.py

# 代码检查
uv run ruff check main.py
uv run ruff format main.py
uv run pyright main.py

# Git 操作
git status
pre-commit run --all-files
```

---

## 文件结构

```
.devcontainer/
├── devcontainer.json        # VS Code 配置
├── Dockerfile               # 镜像定义
├── README.md                # 使用指南（中文）
├── QUICK_START.md           # 快速参考（中文）
└── docs/i18n/
    ├── readme/              # 使用指南翻译
    │   └── README.{en,ja,ko,fr,de}.md
    └── quick-start/         # 快速参考翻译
        └── QUICK_START.{en,ja,ko,fr,de}.md
```

---

## 快速测试

```bash
# 测试 Python
docker run --rm jarvis-dev python --version

# 测试 uv
docker run --rm jarvis-dev uv --version

# 测试 Bun
docker run --rm jarvis-dev bun --version
```

---

## 故障排除

| 问题 | 解决方案 |
|------|----------|
| Docker 未运行 | 启动 Docker Desktop |
| 构建失败 | `docker system prune -a` 清理缓存 |
| VS Code 无法连接 | 重启 VS Code 或重建容器 |
| 依赖未找到 | 使用 `uv run python` 而非 `python` |

---

## 环境信息

- **Python**: 3.13
- **uv**: latest
- **Bun**: latest
- **Git**: latest
- **基础镜像**: python:3.13-slim
- **用户**: vscode (非 root)
- **工作目录**: /workspace

---

## 相关文档

- [完整使用指南](README.md)

---

**提示**: 首次构建约需 3-5 分钟,后续启动仅需 10-20 秒!
