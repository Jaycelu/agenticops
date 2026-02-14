#!/bin/bash

# NetOps AI 智能运维工作台 - Streamlit 启动脚本

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
python3 -c "import streamlit, langchain" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 依赖未安装，请运行："
    echo "   pip3 install streamlit langchain langchain-openai langchain-core langchain-community"
    exit 1
fi
echo "✅ 依赖检查完成"
echo ""

# 进入 Streamlit 目录
echo "[2/3] 切换到 Streamlit 目录..."
cd frontend/streamlit
echo "✅ 目录切换完成"
echo ""

# 启动 Streamlit（使用原前端端口 5173）
echo "[3/3] 启动 Streamlit 应用（替换原 Vue 3 前端）..."
echo ""
echo "=========================================================="
echo "🌐 访问地址："
echo "   本地: http://localhost:5173"
echo "   远程: http://$(hostname -I | awk '{print $1}'):5173"
echo "=========================================================="
echo ""
echo "💡 提示：按 Ctrl+C 停止服务"
echo ""

streamlit run app.py --server.port 5173 --server.address 0.0.0.0