#!/bin/bash

# NetOps AI 智能运维工作台 - 服务管理脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 端口配置
BACKEND_PORT=8000
FRONTEND_PORT=5173

# 服务名称
BACKEND_SERVICE="netops-backend"
FRONTEND_SERVICE="netops-frontend"
STREAMLIT_PROCESS="streamlit run app.py"

# 显示菜单
show_menu() {
    echo "============================================================"
    echo "🚀 NetOps AI 智能运维工作台 - 服务管理"
    echo "============================================================"
    echo ""
    echo "📊 当前端口配置："
    echo "   - 后端 API: $BACKEND_PORT (FastAPI)"
    echo "   - 前端界面: $FRONTEND_PORT (Streamlit AI)"
    echo ""
    echo "============================================================"
    echo "请选择操作："
    echo "============================================================"
    echo "  1) 📋 查看服务状态"
    echo "  2) ▶️  启动所有服务"
    echo "  3) ⏸️  停止所有服务"
    echo "  4) 🔄 重启所有服务"
    echo "  5) ▶️  只启动后端 (FastAPI)"
    echo "  6) ▶️  只启动前端 (Streamlit)"
    echo "  7) ⏸️  只停止后端"
    echo "  8) ⏸️  只停止前端"
    echo "  0) 🚪 退出"
    echo "============================================================"
    echo -n "请输入选项 [0-8]: "
}

# 检查端口状态
check_port() {
    local port=$1
    local service_name=$2
    
    if netstat -tlnp 2>/dev/null | grep -q ":$port " || ss -tlnp 2>/dev/null | grep -q ":$port "; then
        local pid=$(netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $7}' | cut -d'/' -f1)
        echo -e "  ✅ ${GREEN}$service_name${NC} (端口 $port) - 运行中 [PID: $pid]"
        return 0
    else
        echo -e "  ❌ ${RED}$service_name${NC} (端口 $port) - 未运行"
        return 1
    fi
}

# 查看服务状态
show_status() {
    echo ""
    echo "============================================================"
    echo "📊 服务状态"
    echo "============================================================"
    
    local backend_running=false
    local frontend_running=false
    
    check_port $BACKEND_PORT "FastAPI 后端" && backend_running=true
    check_port $FRONTEND_PORT "Streamlit 前端" && frontend_running=true
    
    echo ""
    echo "============================================================"
    if [ "$backend_running" = true ] && [ "$frontend_running" = true ]; then
        echo -e "${GREEN}✅ 所有服务运行正常${NC}"
    elif [ "$backend_running" = true ] || [ "$frontend_running" = true ]; then
        echo -e "${YELLOW}⚠️  部分服务运行中${NC}"
    else
        echo -e "${RED}❌ 所有服务已停止${NC}"
    fi
    echo "============================================================"
    
    echo ""
    echo "🌐 访问地址："
    if [ "$backend_running" = true ]; then
        echo "   - API 文档: http://localhost:$BACKEND_PORT/docs"
    fi
    if [ "$frontend_running" = true ]; then
        echo "   - AI 运维界面: http://localhost:$FRONTEND_PORT"
        local server_ip=$(hostname -I | awk '{print $1}')
        if [ ! -z "$server_ip" ]; then
            echo "   - 远程访问: http://$server_ip:$FRONTEND_PORT"
        fi
    fi
    echo ""
}

# 启动后端
start_backend() {
    echo ""
    echo "============================================================"
    echo "▶️  启动 FastAPI 后端..."
    echo "============================================================"
    
    if netstat -tlnp 2>/dev/null | grep -q ":$BACKEND_PORT " || ss -tlnp 2>/dev/null | grep -q ":$BACKEND_PORT "; then
        echo -e "${YELLOW}⚠️  FastAPI 后端已在运行${NC}"
        return
    fi
    
    cd /opt/netops/backend
    nohup python3 main.py > ../logs/backend.log 2>&1 &
    sleep 3
    
    if netstat -tlnp 2>/dev/null | grep -q ":$BACKEND_PORT " || ss -tlnp 2>/dev/null | grep -q ":$BACKEND_PORT "; then
        echo -e "${GREEN}✅ FastAPI 后端启动成功${NC}"
    else
        echo -e "${RED}❌ FastAPI 后端启动失败，请查看日志："
        echo "   tail -f /opt/netops/logs/backend.log${NC}"
    fi
}

# 停止后端
stop_backend() {
    echo ""
    echo "============================================================"
    echo "⏸️  停止 FastAPI 后端..."
    echo "============================================================"
    
    local pid=$(netstat -tlnp 2>/dev/null | grep ":$BACKEND_PORT " | awk '{print $7}' | cut -d'/' -f1)
    if [ ! -z "$pid" ]; then
        kill $pid
        sleep 2
        if ! netstat -tlnp 2>/dev/null | grep -q ":$BACKEND_PORT " && ! ss -tlnp 2>/dev/null | grep -q ":$BACKEND_PORT "; then
            echo -e "${GREEN}✅ FastAPI 后端已停止${NC}"
        else
            echo -e "${RED}❌ FastAPI 后端停止失败，尝试强制停止...${NC}"
            kill -9 $pid
        fi
    else
        echo -e "${YELLOW}⚠️  FastAPI 后端未运行${NC}"
    fi
}

# 启动前端
start_frontend() {
    echo ""
    echo "============================================================"
    echo "▶️  启动 Streamlit 前端..."
    echo "============================================================"
    
    if netstat -tlnp 2>/dev/null | grep -q ":$FRONTEND_PORT " || ss -tlnp 2>/dev/null | grep -q ":$FRONTEND_PORT "; then
        echo -e "${YELLOW}⚠️  Streamlit 前端已在运行${NC}"
        return
    fi
    
    cd /opt/netops/frontend/streamlit
    echo "" | nohup streamlit run app.py --server.port $FRONTEND_PORT --server.address 0.0.0.0 --server.headless true > ../../logs/streamlit.log 2>&1 &
    sleep 5
    
    if netstat -tlnp 2>/dev/null | grep -q ":$FRONTEND_PORT " || ss -tlnp 2>/dev/null | grep -q ":$FRONTEND_PORT "; then
        echo -e "${GREEN}✅ Streamlit 前端启动成功${NC}"
    else
        echo -e "${RED}❌ Streamlit 前端启动失败，请查看日志："
        echo "   tail -f /opt/netops/logs/streamlit.log${NC}"
    fi
}

# 停止前端
stop_frontend() {
    echo ""
    echo "============================================================"
    echo "⏸️  停止 Streamlit 前端..."
    echo "============================================================"
    
    local pid=$(netstat -tlnp 2>/dev/null | grep ":$FRONTEND_PORT " | awk '{print $7}' | cut -d'/' -f1)
    if [ ! -z "$pid" ]; then
        kill $pid
        sleep 2
        if ! netstat -tlnp 2>/dev/null | grep -q ":$FRONTEND_PORT " && ! ss -tlnp 2>/dev/null | grep -q ":$FRONTEND_PORT "; then
            echo -e "${GREEN}✅ Streamlit 前端已停止${NC}"
        else
            echo -e "${RED}❌ Streamlit 前端停止失败，尝试强制停止...${NC}"
            kill -9 $pid
        fi
    else
        echo -e "${YELLOW}⚠️  Streamlit 前端未运行${NC}"
    fi
}

# 启动所有服务
start_all() {
    echo ""
    echo "============================================================"
    echo "▶️  启动所有服务..."
    echo "============================================================"
    start_backend
    start_frontend
    show_status
}

# 停止所有服务
stop_all() {
    echo ""
    echo "============================================================"
    echo "⏸️  停止所有服务..."
    echo "============================================================"
    stop_frontend
    stop_backend
    echo -e "${GREEN}✅ 所有服务已停止${NC}"
}

# 重启所有服务
restart_all() {
    echo ""
    echo "============================================================"
    echo "🔄 重启所有服务..."
    echo "============================================================"
    stop_all
    sleep 2
    start_all
}

# 主循环
main() {
    while true; do
        show_menu
        read choice
        
        case $choice in
            1)
                show_status
                ;;
            2)
                start_all
                ;;
            3)
                stop_all
                ;;
            4)
                restart_all
                ;;
            5)
                start_backend
                show_status
                ;;
            6)
                start_frontend
                show_status
                ;;
            7)
                stop_backend
                show_status
                ;;
            8)
                stop_frontend
                show_status
                ;;
            0)
                echo ""
                echo "👋 再见！"
                exit 0
                ;;
            *)
                echo -e "${RED}❌ 无效选项，请重新选择${NC}"
                ;;
        esac
        
        echo ""
        echo -n "按 Enter 键继续..."
        read
        clear
    done
}

# 检查是否在项目根目录
if [ ! -f "backend/main.py" ]; then
    echo -e "${RED}❌ 错误：请在项目根目录（/opt/netops）运行此脚本${NC}"
    exit 1
fi

# 创建日志目录
mkdir -p logs

# 运行主程序
main