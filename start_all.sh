#!/bin/bash

# NetOps AI 智能运维工作台 - 一键启动脚本

echo "============================================================"
echo "🚀 NetOps AI 智能运维工作台 - 一键启动"
echo "============================================================"
echo ""

# 检查是否在项目根目录
if [ ! -f "backend/main.py" ]; then
    echo "❌ 错误：请在项目根目录（/opt/netops）运行此脚本"
    exit 1
fi

# 检查依赖
echo "[1/4] 检查依赖..."
python3 -c "import streamlit, langchain" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 依赖未安装"
    exit 1
fi
echo "✅ 依赖检查完成"
echo ""

# 启动后端
echo "[2/4] 启动 FastAPI 后端（端口 8000）..."
cd backend
nohup python3 main.py > ../logs/backend.log 2>&1 &
cd ..
sleep 3
if netstat -tlnp 2>/dev/null | grep -q ":8000 " || ss -tlnp 2>/dev/null | grep -q ":8000 "; then
    echo "✅ FastAPI 后端启动成功"
else
    echo "❌ FastAPI 后端启动失败"
fi
echo ""

# 启动前端
echo "[3/4] 启动 Streamlit 前端（端口 8501）..."
cd frontend/streamlit
echo "" | nohup streamlit run app.py --server.port 5173 --server.address 0.0.0.0 --server.headless true > ../../logs/streamlit.log 2>&1 &
cd ../..
sleep 5
if netstat -tlnp 2>/dev/null | grep -q ":5173 " || ss -tlnp 2>/dev/null | grep -q ":5173 "; then
    echo "✅ Streamlit 前端启动成功"
else
    echo "❌ Streamlit 前端启动失败"
fi
echo ""

# 显示访问地址
echo "[4/4] 显示访问地址..."
echo ""
echo "============================================================"
echo "🌐 访问地址"
echo "============================================================"
echo "   AI 运维界面: http://10.128.206.214:8501"
echo "   本地访问:   http://localhost:8501"
echo ""
echo "   API 文档:   http://10.128.206.214:8000/docs"
echo "   本地 API:   http://localhost:8000/docs"
echo "============================================================"
echo ""
echo "💡 提示："
echo "   - 使用 './manage_services.sh' 管理服务"
echo "   - 查看日志: tail -f logs/backend.log 或 logs/streamlit.log"
echo "   - 停止服务: ./manage_services.sh 选择选项 3"
echo ""
echo "✅ 启动完成！"
echo "============================================================"