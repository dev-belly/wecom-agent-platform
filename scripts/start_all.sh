#!/bin/bash
# 一键启动：vLLM + API Service
# 用法: bash scripts/start_all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

mkdir -p logs

echo "=== Step 1/2: 启动 vLLM ==="
bash scripts/start_vllm.sh ${1:-0} &
VLLM_PID=$!
sleep 5

echo ""
echo "=== Step 2/2: 启动 API Service ==="
python -m uvicorn src.main:app --host 0.0.0.0 --port 9000 --reload 2>&1 | tee logs/api_9000.log &
API_PID=$!
echo $API_PID > /tmp/api_service.pid

echo ""
echo "============================================"
echo "  全部服务已启动"
echo "  vLLM:     http://localhost:8000"
echo "  API:      http://localhost:9000"
echo "  API Docs: http://localhost:9000/docs"
echo "============================================"
echo ""
echo "PID 文件:"
echo "  vLLM: /tmp/vllm.pid ($VLLM_PID)"
echo "  API:  /tmp/api_service.pid ($API_PID)"
echo ""
echo "停止: kill \$(cat /tmp/vllm.pid) \$(cat /tmp/api_service.pid)"

wait
