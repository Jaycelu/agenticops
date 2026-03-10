#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================================="
echo "AgenticOps 前端启动脚本"
echo "=========================================================="

if [ ! -f "$ROOT_DIR/frontend/package.json" ]; then
    echo "错误：请在项目根目录运行此脚本"
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "错误：缺少 npm"
    exit 1
fi

cd "$ROOT_DIR/frontend"
echo "前端地址: http://localhost:5173"
npm run dev -- --host 0.0.0.0 --port 5173
