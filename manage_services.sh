#!/bin/bash

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
BACKEND_PORT=8000
FRONTEND_PORT=5173

mkdir -p "$LOG_DIR"

show_menu() {
    echo "============================================================"
    echo "AgenticOps - 服务管理"
    echo "============================================================"
    echo "1) 查看服务状态"
    echo "2) 启动所有服务"
    echo "3) 停止所有服务"
    echo "4) 重启所有服务"
    echo "5) 只启动后端"
    echo "6) 只启动前端"
    echo "7) 只停止后端"
    echo "8) 只停止前端"
    echo "0) 退出"
    echo -n "请输入选项 [0-8]: "
}

port_running() {
    local port=$1
    netstat -tlnp 2>/dev/null | grep -q ":$port " || ss -tlnp 2>/dev/null | grep -q ":$port "
}

show_status() {
    echo "------------------------------------------------------------"
    if port_running "$BACKEND_PORT"; then
        echo -e "${GREEN}后端运行中${NC}: http://localhost:$BACKEND_PORT/docs"
    else
        echo -e "${RED}后端未运行${NC}"
    fi

    if port_running "$FRONTEND_PORT"; then
        echo -e "${GREEN}前端运行中${NC}: http://localhost:$FRONTEND_PORT"
    else
        echo -e "${RED}前端未运行${NC}"
    fi
    echo "------------------------------------------------------------"
}

start_backend() {
    if port_running "$BACKEND_PORT"; then
        echo -e "${YELLOW}后端已在运行${NC}"
        return
    fi

    (
        cd "$ROOT_DIR/backend"
        nohup python3 main.py > "$LOG_DIR/backend.log" 2>&1 &
    )
    sleep 3
    echo -e "${GREEN}后端已启动${NC}"
}

start_frontend() {
    if port_running "$FRONTEND_PORT"; then
        echo -e "${YELLOW}前端已在运行${NC}"
        return
    fi

    (
        cd "$ROOT_DIR/frontend"
        nohup npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" > "$LOG_DIR/frontend.log" 2>&1 &
    )
    sleep 5
    echo -e "${GREEN}前端已启动${NC}"
}

stop_backend() {
    local pid
    pid="$(netstat -tlnp 2>/dev/null | grep ":$BACKEND_PORT " | awk '{print $7}' | cut -d'/' -f1 || true)"
    if [ -n "${pid:-}" ]; then
        kill "$pid" || true
        sleep 2
        echo -e "${GREEN}后端已停止${NC}"
    else
        echo -e "${YELLOW}后端未运行${NC}"
    fi
}

stop_frontend() {
    local pid
    pid="$(netstat -tlnp 2>/dev/null | grep ":$FRONTEND_PORT " | awk '{print $7}' | cut -d'/' -f1 || true)"
    if [ -n "${pid:-}" ]; then
        kill "$pid" || true
        sleep 2
        echo -e "${GREEN}前端已停止${NC}"
    else
        echo -e "${YELLOW}前端未运行${NC}"
    fi
}

start_all() {
    start_backend
    start_frontend
    show_status
}

stop_all() {
    stop_frontend
    stop_backend
    show_status
}

restart_all() {
    stop_all
    start_all
}

if [ ! -f "$ROOT_DIR/backend/main.py" ]; then
    echo -e "${RED}错误：请在项目根目录运行此脚本${NC}"
    exit 1
fi

while true; do
    show_menu
    read -r choice
    case "$choice" in
        1) show_status ;;
        2) start_all ;;
        3) stop_all ;;
        4) restart_all ;;
        5) start_backend; show_status ;;
        6) start_frontend; show_status ;;
        7) stop_backend; show_status ;;
        8) stop_frontend; show_status ;;
        0) exit 0 ;;
        *) echo -e "${RED}无效选项${NC}" ;;
    esac
done
