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
if ! command -v python3 >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "❌ 缺少 python3 或 npm"
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
echo "[3/4] 启动 Vue 前端（端口 5173）..."
cd frontend
nohup npm run dev -- --host 0.0.0.0 --port 5173 > ../logs/frontend.log 2>&1 &
cd ..
sleep 5
if netstat -tlnp 2>/dev/null | grep -q ":5173 " || ss -tlnp 2>/dev/null | grep -q ":5173 "; then
    echo "✅ Vue 前端启动成功"
else
    echo "❌ Vue 前端启动失败"
fi
echo ""

# 显示访问地址
echo "[4/4] 显示访问地址..."
echo ""
echo "============================================================"
echo "🌐 访问地址"
echo "============================================================"
echo "   AI 运维界面: http://10.128.206.214:5173"
echo "   本地访问:   http://localhost:5173"
echo ""
echo "   API 文档:   http://10.128.206.214:8000/docs"
echo "   本地 API:   http://localhost:8000/docs"
echo "============================================================"
echo ""
echo "💡 提示："
echo "   - 使用 './manage_services.sh' 管理服务"
echo "   - 查看日志: tail -f logs/backend.log 或 logs/frontend.log"
echo "   - 停止服务: ./manage_services.sh 选择选项 3"
echo ""
echo "✅ 启动完成！"
echo "============================================================"
