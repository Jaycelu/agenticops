#!/bin/bash

# NetOps AI 智能运维工作台 - 前端启动脚本

echo "=========================================================="
echo "🚀 NetOps AI 智能运维工作台"
echo "=========================================================="
echo ""

# 检查是否在项目根目录
if [ ! -f "backend/main.py" ]; then
    echo "❌ 错误：请在项目根目录（/opt/netops）运行此脚本"
    exit 1
fi

# 检查依赖
echo "[1/3] 检查依赖..."
if ! command -v npm >/dev/null 2>&1; then
    echo "❌ 依赖未安装，请先安装 npm"
    exit 1
fi
echo "✅ 依赖检查完成"
echo ""

# 进入前端目录
echo "[2/3] 切换到前端目录..."
cd frontend
echo "✅ 目录切换完成"
echo ""

# 启动前端
echo "[3/3] 启动 Vue 应用..."
echo ""
echo "=========================================================="
echo "🌐 访问地址："
echo "   本地: http://localhost:5173"
echo "   远程: http://$(hostname -I | awk '{print $1}'):5173"
echo "=========================================================="
echo ""
echo "💡 提示：按 Ctrl+C 停止服务"
echo ""

npm run dev -- --host 0.0.0.0 --port 5173
