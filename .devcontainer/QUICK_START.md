# 🚀 Dev Container 快速参考

## 一键启动 (VS Code)

```bash
# 1. 打开 VS Code
code /Users/hyh/code/agents

# 2. 按 F1,输入:
Dev Containers: Reopen in Container

# 3. 等待构建完成,开始编码!
```

---

## 命令行使用

### 构建镜像
```bash
cd /Users/hyh/code/agents
docker build -t agents-dev -f .devcontainer/Dockerfile .
```

### 运行程序
```bash
docker run --rm \
  -v $(pwd):/workspace \
  agents-dev \
  bash -c "cd /workspace && uv sync && uv run python main.py"
```

### 进入交互式 Shell
```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -w /workspace \
  agents-dev bash
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
├── devcontainer.json     # VS Code 配置
├── Dockerfile            # 镜像定义
├── README.md             # 使用指南
├── CHANGELOG.md          # 配置日志
├── SETUP_COMPLETE.md     # 完整报告
├── TEST_REPORT.md        # 测试结果
└── test.sh               # 验证脚本
```

---

## 快速测试

```bash
# 验证配置
./.devcontainer/test.sh

# 测试 Python
docker run --rm agents-dev python --version

# 测试 uv
docker run --rm agents-dev uv --version

# 测试完整流程
docker run --rm -v $(pwd):/workspace agents-dev \
  bash -c "cd /workspace && uv sync && uv run python main.py"
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

- **Python**: 3.13.11
- **uv**: 0.9.26
- **Git**: 2.47.3
- **基础镜像**: python:3.13-slim
- **用户**: vscode (非 root)
- **工作目录**: /workspace

---

## 相关文档

- [完整使用指南](.devcontainer/README.md)
- [配置说明](.devcontainer/CHANGELOG.md)
- [测试报告](.devcontainer/TEST_REPORT.md)
- [完整设置报告](.devcontainer/SETUP_COMPLETE.md)

---

**提示**: 首次构建约需 3-5 分钟,后续启动仅需 10-20 秒!
