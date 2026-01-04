#!/bin/bash
set -e

echo "🚀 小易猜猜开发环境初始化中..."

# 进入工作目录
cd /workspace

# 安装 pnpm（如果还没安装）
if ! command -v pnpm &> /dev/null; then
    echo "📦 安装 pnpm..."
    curl -fsSL https://get.pnpm.io/install.sh | sh -
    export PNPM_HOME="/root/.local/share/pnpm"
    export PATH="${PNPM_HOME}:${PATH}"
fi

# 安装前端依赖
if [ -d "apps/web" ]; then
    echo "📦 安装前端依赖..."
    cd apps/web
    pnpm install
    cd /workspace
fi

# 安装后端依赖
if [ -d "apps/api" ]; then
    echo "🐍 安装后端依赖..."
    cd apps/api
    pip install -r requirements.txt --break-system-packages
    cd /workspace
fi

# 复制环境变量文件
if [ -f ".env.example" ] && [ ! -f ".env" ]; then
    echo "📝 创建 .env 文件..."
    cp .env.example .env
fi

echo ""
echo "✅ 开发环境初始化完成！"
echo ""
echo "🎯 快速开始:"
echo "   前端: cd apps/web && pnpm dev"
echo "   后端: cd apps/api && python -m uvicorn app.main:app --reload"
echo ""
echo "🔗 访问地址:"
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:8000"
echo "   API文档: http://localhost:8000/docs"
echo ""
