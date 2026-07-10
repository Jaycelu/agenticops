#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
BACKEND_PORT=8000
FRONTEND_PORT=5173

mkdir -p "$LOG_DIR"

echo "============================================================"
echo "AgenticOps - 一键启动"
echo "============================================================"

if [ ! -f "$ROOT_DIR/backend/main.py" ]; then
    echo "错误：请在项目根目录运行此脚本"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "错误：缺少 python3"
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "错误：缺少 npm"
    exit 1
fi

echo "[1/4] 启动 FastAPI 后端..."
(
    cd "$ROOT_DIR/backend"
    alembic upgrade head
    nohup python3 main.py > "$LOG_DIR/backend.log" 2>&1 &
)
sleep 3

echo "[2/4] 启动 Vue 前端..."
(
    cd "$ROOT_DIR/frontend"
    nohup npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" > "$LOG_DIR/frontend.log" 2>&1 &
)
sleep 5

echo "[3/4] 本地访问地址"
echo "前端: http://localhost:$FRONTEND_PORT"
echo "后端文档: http://localhost:$BACKEND_PORT/docs"
echo "健康检查: http://localhost:$BACKEND_PORT/health"

if command -v hostname >/dev/null 2>&1; then
    SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    if [ -n "${SERVER_IP:-}" ]; then
        echo "[4/4] 局域网访问地址"
        echo "前端: http://$SERVER_IP:$FRONTEND_PORT"
        echo "后端文档: http://$SERVER_IP:$BACKEND_PORT/docs"
    fi
fi

echo "日志目录: $LOG_DIR"
