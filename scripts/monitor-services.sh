#!/bin/bash

# NetOps 服务监控脚本
# 检查前后端服务状态，如果服务挂了会自动重启

LOG_FILE="/opt/netops/logs/service_monitor.log"
BACKEND_URL="http://localhost:8000/health"
FRONTEND_URL="http://localhost:5173"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

check_backend() {
    if curl -sf "$BACKEND_URL" > /dev/null 2>&1; then
        log "Backend is healthy"
        return 0
    else
        log "Backend is DOWN, attempting to restart..."
        systemctl restart netops-backend
        return 1
    fi
}

check_frontend() {
    if curl -sf "$FRONTEND_URL" > /dev/null 2>&1; then
        log "Frontend is healthy"
        return 0
    else
        log "Frontend is DOWN, attempting to restart..."
        systemctl restart netops-frontend
        return 1
    fi
}

# 主监控逻辑
log "=== Starting service health check ==="
check_backend
check_frontend
log "=== Service health check completed ==="