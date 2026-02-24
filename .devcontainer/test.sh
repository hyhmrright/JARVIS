#!/bin/bash

# Dev Container 配置测试脚本

echo "🔍 检查 Dev Container 配置..."
echo ""

# 检查必需文件
FILES=(
    ".devcontainer/devcontainer.json"
    ".devcontainer/Dockerfile"
    ".dockerignore"
)

echo "📁 检查必需文件:"
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file 不存在"
    fi
done

echo ""
echo "🐳 检查 Docker 状态:"
if docker info > /dev/null 2>&1; then
    echo "  ✅ Docker 正在运行"
    echo "  版本: $(docker --version)"
else
    echo "  ❌ Docker 未运行"
    echo "  请启动 Docker Desktop"
fi

echo ""
echo "📦 构建测试 (可选):"
echo "  运行以下命令测试 Dockerfile 构建:"
echo "  docker build -t jarvis-dev -f .devcontainer/Dockerfile ."
echo ""
echo "🚀 VS Code 使用:"
echo "  1. 安装 'Dev Containers' 扩展"
echo "  2. 按 F1 → 输入 'Dev Containers: Reopen in Container'"
echo "  3. 等待容器构建完成"
echo ""
echo "✅ Dev Container 配置已完成！"
