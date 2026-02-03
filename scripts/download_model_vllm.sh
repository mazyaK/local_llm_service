#!/usr/bin/env bash
# =============================================================================
# Предзагрузка модели для vLLM (Hugging Face)
# 
# Использование:
#   ./scripts/download_model_vllm.sh [MODEL_ID]
#
# Примеры:
#   ./scripts/download_model_vllm.sh Qwen/Qwen3-8B-AWQ
#   ./scripts/download_model_vllm.sh Qwen/Qwen3-8B
#   HF_TOKEN=... ./scripts/download_model_vllm.sh meta-llama/Llama-3.3-70B-Instruct
#
# Переменные окружения:
#   HF_TOKEN       - токен Hugging Face (для gated моделей)
#   HF_CACHE_DIR   - каталог кэша HF (по умолчанию: ~/.cache/huggingface)
# =============================================================================
set -euo pipefail

MODEL_ID="${1:-${VLLM_MODEL:-}}"

if [[ -z "${MODEL_ID}" ]]; then
    echo "Ошибка: не указан MODEL_ID"
    echo ""
    echo "Использование:"
    echo "  ./scripts/download_model_vllm.sh <MODEL_ID>"
    echo ""
    echo "Примеры:"
    echo "  ./scripts/download_model_vllm.sh Qwen/Qwen3-8B-AWQ"
    echo "  ./scripts/download_model_vllm.sh Qwen/Qwen3-8B"
    exit 2
fi

CACHE_DIR="${HF_CACHE_DIR:-${HOME}/.cache/huggingface}"

echo "============================================="
echo "Предзагрузка модели для vLLM"
echo "Модель:  ${MODEL_ID}"
echo "Кэш HF:  ${CACHE_DIR}"
echo "============================================="

# Создаём каталог кэша, если не существует
mkdir -p "${CACHE_DIR}"

# Скачиваем модель через huggingface-cli
docker run --rm \
    -e HUGGING_FACE_HUB_TOKEN="${HF_TOKEN:-}" \
    -v "$(realpath "${CACHE_DIR}"):/root/.cache/huggingface" \
    python:3.11-slim \
    bash -c "
        pip install -q --no-cache-dir 'huggingface-hub>=0.20.0' && \
        huggingface-cli download '${MODEL_ID}'
    "

echo ""
echo "============================================="
echo "Готово!"
echo "Модель '${MODEL_ID}' скачана в кэш HF: ${CACHE_DIR}"
echo ""
echo "Для запуска vLLM выполните:"
echo "  docker compose --profile vllm up -d"
echo "============================================="
