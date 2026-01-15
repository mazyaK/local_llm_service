#!/usr/bin/env bash
set -euo pipefail

# Скачивает модель в ./data, чтобы контейнер vLLM мог переиспользовать её (без повторной загрузки при рестарте).
#
# Использование:
#   HF_TOKEN=... ./download_model.sh Qwen/Qwen3-8B
#   ./download_model.sh Qwen/Qwen3-8B
#
# Результат:
#   ./data/models/Qwen3-8B/  (или имя папки, полученное из model id)

MODEL_ID="${1:-Qwen/Qwen3-8B}"
SAFE_DIR_NAME="$(echo "${MODEL_ID}" | tr '/:' '__')"

mkdir -p "./data/models/${SAFE_DIR_NAME}"
mkdir -p "./data/hf"

echo "Скачивание: ${MODEL_ID}"
echo "Каталог:    ./data/models/${SAFE_DIR_NAME}"

# Используем временный контейнер, чтобы не ставить huggingface-cli на хост.
docker run --rm \
  -e HUGGING_FACE_HUB_TOKEN="${HF_TOKEN:-}" \
  -v "$(pwd)/data:/data" \
  python:3.11-slim \
  bash -lc "pip -q install --no-cache-dir 'huggingface-hub==0.27.1' && \
            python -m huggingface_hub.cli download '${MODEL_ID}' \
              --local-dir '/data/models/${SAFE_DIR_NAME}' \
              --local-dir-use-symlinks False"

echo
echo "Готово."
echo "Если хотите, чтобы vLLM грузил модель с диска, пропишите в .env:"
echo "  MODEL_NAME=/data/models/${SAFE_DIR_NAME}"

