#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/service_monitor.log"
BACKEND_URL="http://localhost:8000/health"
FRONTEND_URL="http://localhost:5173"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

check_backend() {
    if curl -sf "$BACKEND_URL" > /dev/null 2>&1; then
        log "Backend is healthy"
        return 0
    else
        log "Backend is DOWN, attempting to restart..."
        systemctl restart agenticops-backend.service
        return 1
    fi
}

check_frontend() {
    if curl -sf "$FRONTEND_URL" > /dev/null 2>&1; then
        log "Frontend is healthy"
        return 0
    else
        log "Frontend is DOWN, attempting to restart..."
        systemctl restart agenticops-frontend.service
        return 1
    fi
}

# 主监控逻辑
log "=== Starting service health check ==="
check_backend
check_frontend
log "=== Service health check completed ==="
