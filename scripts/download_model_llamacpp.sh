#!/usr/bin/env bash
# =============================================================================
# Скачивание GGUF-модели для llama.cpp
# 
# Использование:
#   ./scripts/download_model_llamacpp.sh [HF_REPO] [FILENAME]
#
# Примеры:
#   ./scripts/download_model_llamacpp.sh Qwen/Qwen3-8B-GGUF qwen3-8b-q4_k_m.gguf
#   ./scripts/download_model_llamacpp.sh bartowski/Qwen3-8B-GGUF Qwen3-8B-Q4_K_M.gguf
#
# Переменные окружения:
#   HF_TOKEN              - токен Hugging Face (для gated моделей)
#   LLAMACPP_MODELS_DIR   - каталог для моделей (по умолчанию: ./data/llamacpp)
# =============================================================================
set -euo pipefail

HF_REPO="${1:-}"
FILENAME="${2:-}"

if [[ -z "${HF_REPO}" ]] || [[ -z "${FILENAME}" ]]; then
    echo "Ошибка: не указаны HF_REPO и/или FILENAME"
    echo ""
    echo "Использование:"
    echo "  ./scripts/download_model_llamacpp.sh <HF_REPO> <FILENAME>"
    echo ""
    echo "Примеры:"
    echo "  ./scripts/download_model_llamacpp.sh Qwen/Qwen3-8B-GGUF qwen3-8b-q4_k_m.gguf"
    echo "  ./scripts/download_model_llamacpp.sh bartowski/Qwen3-8B-GGUF Qwen3-8B-Q4_K_M.gguf"
    echo ""
    echo "Популярные GGUF-модели Qwen3:"
    echo "  - Qwen/Qwen3-8B-GGUF (официальные)"
    echo "  - bartowski/Qwen3-8B-GGUF (community quantizations)"
    exit 2
fi

MODELS_DIR="${LLAMACPP_MODELS_DIR:-./data/llamacpp}"
OUTPUT_PATH="${MODELS_DIR}/${FILENAME}"

echo "============================================="
echo "Скачивание GGUF-модели для llama.cpp"
echo "Репозиторий: ${HF_REPO}"
echo "Файл:        ${FILENAME}"
echo "Каталог:     ${MODELS_DIR}"
echo "============================================="

# Создаём каталог, если не существует
mkdir -p "${MODELS_DIR}"

# Проверяем, не скачан ли уже файл
if [[ -f "${OUTPUT_PATH}" ]]; then
    echo "Файл уже существует: ${OUTPUT_PATH}"
    echo "Удалите его вручную, если хотите скачать заново."
    exit 0
fi

# Скачиваем через huggingface-cli в Docker
docker run --rm \
    -e HUGGING_FACE_HUB_TOKEN="${HF_TOKEN:-}" \
    -v "$(realpath "${MODELS_DIR}"):/models" \
    python:3.11-slim \
    bash -c "
        pip install -q --no-cache-dir 'huggingface-hub>=0.20.0' && \
        huggingface-cli download '${HF_REPO}' '${FILENAME}' \
            --local-dir /models \
            --local-dir-use-symlinks False
    "

echo ""
echo "============================================="
echo "Готово!"
echo "Модель скачана: ${OUTPUT_PATH}"
echo ""
echo "Для запуска llama.cpp обновите .env:"
echo "  LLAMACPP_MODEL_FILE=${FILENAME}"
echo ""
echo "Затем выполните:"
echo "  docker compose --profile llamacpp up -d"
echo "============================================="
