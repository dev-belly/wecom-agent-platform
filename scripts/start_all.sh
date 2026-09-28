#!/bin/bash
# 一键启动：vLLM + API Service
# 用法: bash scripts/start_all.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

mkdir -p logs

echo "=== Step 1/2: 启动 vLLM ==="
bash scripts/start_vllm.sh "${1:-0}"
VLLM_PID="$(cat logs/vllm.pid)"

cleanup() {
    if [ -n "${API_PID:-}" ]; then
        kill "${API_PID}" 2>/dev/null || true
    fi
    kill "${VLLM_PID}" 2>/dev/null || true
    rm -f logs/api.pid logs/vllm.pid
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo ""
echo "=== Step 2/2: 启动 API Service ==="
python -m uvicorn src.main:app --host 127.0.0.1 --port 9000 > logs/api_9000.log 2>&1 &
API_PID=$!
echo "${API_PID}" > logs/api.pid

for i in $(seq 1 30); do
    if ! kill -0 "${API_PID}" 2>/dev/null; then
        echo "API 启动失败，请检查日志: logs/api_9000.log" >&2
        exit 1
    fi
    if curl -fsS http://127.0.0.1:9000/health > /dev/null 2>&1; then
        break
    fi
    if [ "${i}" -eq 30 ]; then
        echo "API 启动超时，请检查日志: logs/api_9000.log" >&2
        exit 1
    fi
    sleep 1
done

echo ""
echo "============================================"
echo "  全部服务已启动"
echo "  vLLM:     http://localhost:8000"
echo "  API:      http://localhost:9000"
echo "  API Docs: http://localhost:9000/docs"
echo "============================================"
echo ""
echo "PID 文件:"
echo "  vLLM: logs/vllm.pid ($VLLM_PID)"
echo "  API:  logs/api.pid ($API_PID)"
echo ""
echo "按 Ctrl+C 同时停止两个服务。"

wait "${API_PID}"
