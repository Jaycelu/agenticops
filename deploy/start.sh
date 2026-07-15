#!/bin/bash

# NetOps AI Platform 启动脚本

echo "=========================================="
echo "  NetOps AI Platform 启动脚本"
echo "=========================================="

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3，请先安装 Python3"
    exit 1
fi

# 进入后端目录
cd "$(dirname "$0")/../backend"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "安装 Python 依赖..."
pip install -r requirements.txt -q

# 显式升级数据库。应用启动只校验版本，不再自动修改 schema。
echo "升级数据库结构..."
alembic upgrade head

# 启动后端服务
echo "启动后端服务..."
uvicorn main:app --host "${BACKEND_HOST:-0.0.0.0}" --port "${BACKEND_PORT:-8000}" &

BACKEND_PID=$!
echo "后端服务已启动 (PID: $BACKEND_PID)"

echo "启动后台 Worker..."
python3 -m worker &
WORKER_PID=$!
echo "后台 Worker 已启动 (PID: $WORKER_PID)"

cleanup() {
  kill "$BACKEND_PID" "$WORKER_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$WORKER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ""
echo "=========================================="
echo "  服务启动完成！"
echo "=========================================="
echo "后端 API: http://localhost:8000"
echo "API 文档: http://localhost:8000/docs"
echo "健康检查: http://localhost:8000/health"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=========================================="

# 任一关键进程退出都终止启动脚本，避免留下半运行状态。
wait -n "$BACKEND_PID" "$WORKER_PID"
exit 1
