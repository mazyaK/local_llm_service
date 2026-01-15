#!/usr/bin/env bash
set -euo pipefail

MODEL_ID="${1:-Qwen/Qwen3-8B}"
SAFE_DIR_NAME="$(echo "${MODEL_ID}" | tr '/:' '__')"

mkdir -p "./data/models/${SAFE_DIR_NAME}"
mkdir -p "./data/hf"

echo "Скачивание: ${MODEL_ID}"
echo "Каталог:    ./data/models/${SAFE_DIR_NAME}"

docker run --rm \
  -e HUGGING_FACE_HUB_TOKEN="${HF_TOKEN:-}" \
  -v "$(pwd)/data:/data" \
  python:3.11-slim \
  bash -c "
    pip install --no-cache-dir 'huggingface-hub[cli]>=0.20.0' || exit 1
    huggingface-cli download '${MODEL_ID}' \
      --local-dir '/data/models/${SAFE_DIR_NAME}' \
      --local-dir-use-symlinks False
  "

echo
echo "Готово."
echo "Если хотите, чтобы vLLM грузил модель с диска, пропишите в .env:"
echo "  MODEL_NAME=/data/models/${SAFE_DIR_NAME}"