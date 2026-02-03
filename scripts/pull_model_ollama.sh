#!/usr/bin/env bash
# =============================================================================
# Скачивание модели для Ollama
# 
# Использование:
#   ./scripts/pull_model_ollama.sh [MODEL_NAME]
#
# Примеры:
#   ./scripts/pull_model_ollama.sh qwen3:8b
#   ./scripts/pull_model_ollama.sh llama3.3:70b
#   OLLAMA_MODEL=qwen3:8b ./scripts/pull_model_ollama.sh
#
# Скрипт запускает временный контейнер Ollama и скачивает модель в volume.
# =============================================================================
set -euo pipefail

MODEL="${1:-${OLLAMA_MODEL:-qwen3:8b}}"
MODELS_DIR="${OLLAMA_MODELS_DIR:-./data/ollama}"

echo "============================================="
echo "Скачивание модели Ollama: ${MODEL}"
echo "Каталог моделей: ${MODELS_DIR}"
echo "============================================="

# Создаём каталог, если не существует
mkdir -p "${MODELS_DIR}"

# Запускаем Ollama и скачиваем модель
docker run --rm \
    --gpus all \
    -v "$(realpath "${MODELS_DIR}"):/root/.ollama" \
    -e OLLAMA_HOST=0.0.0.0 \
    ollama/ollama:latest \
    sh -c "ollama serve & sleep 5 && ollama pull '${MODEL}' && echo 'Модель скачана успешно!'"

echo ""
echo "============================================="
echo "Готово!"
echo "Модель '${MODEL}' скачана в ${MODELS_DIR}"
echo ""
echo "Для запуска Ollama выполните:"
echo "  docker compose --profile ollama up -d"
echo "============================================="
