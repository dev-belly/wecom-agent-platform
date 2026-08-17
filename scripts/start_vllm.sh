#!/bin/bash
# vLLM Qwen3-14B AWQ 启动脚本
# 用法: bash scripts/start_vllm.sh [GPU_ID]

set -e

GPU_ID=${1:-0}
MODEL_NAME="Qwen/Qwen3-14B-AWQ"
PORT=8000
MAX_MODEL_LEN=8192
GPU_MEMORY_UTILIZATION=0.90

echo "============================================"
echo "  vLLM Qwen3-14B AWQ 启动"
echo "  Model: ${MODEL_NAME}"
echo "  GPU:   ${GPU_ID}"
echo "  Port:  ${PORT}"
echo "============================================"

export CUDA_VISIBLE_DEVICES=${GPU_ID}

# 检查模型是否存在（本地路径或自动下载）
if [ -d "/data/models/${MODEL_NAME}" ]; then
    MODEL_PATH="/data/models/${MODEL_NAME}"
    echo "使用本地模型: ${MODEL_PATH}"
else
    MODEL_PATH="${MODEL_NAME}"
    echo "从 HuggingFace 下载: ${MODEL_PATH}"
fi

python -m vllm.entrypoints.openai.api_server \
    --model "${MODEL_PATH}" \
    --port ${PORT} \
    --max-model-len ${MAX_MODEL_LEN} \
    --gpu-memory-utilization ${GPU_MEMORY_UTILIZATION} \
    --dtype half \
    --quantization awq \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --max-num-seqs 64 \
    --max-num-batched-tokens 8192 \
    --enable-prefix-caching \
    --swap-space 4 \
    --host 0.0.0.0 \
    2>&1 | tee logs/vllm_${PORT}.log &

VLLM_PID=$!
echo "vLLM PID: ${VLLM_PID}"
echo ${VLLM_PID} > /tmp/vllm.pid

echo ""
echo "等待服务就绪..."
for i in $(seq 1 30); do
    if curl -s http://localhost:${PORT}/health > /dev/null 2>&1; then
        echo "✅ vLLM 服务已就绪 (http://localhost:${PORT})"
        echo ""
        echo "测试接口:"
        curl -s http://localhost:${PORT}/v1/models | python -m json.tool || true
        exit 0
    fi
    sleep 2
    echo "  等待中... (${i}/30)"
done

echo "⚠️ 超时，请检查日志: logs/vllm_${PORT}.log"
