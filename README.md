## Локальная LLM + vLLM (A5000 24GB) + OpenAI-совместимый REST API (Docker)

Развёртывание **любой LLM** (из Hugging Face или локальной папки) на **NVIDIA A5000 24GB** с инференсом через **vLLM** и эндпоинтами в формате **OpenAI API**:

- **`/v1/chat/completions`** (включая потоковую выдачу (**SSE**))
- **`/v1/models`**
- **`/health`**

По умолчанию используется официальный образ **`vllm/vllm-openai:latest`** (он уже поднимает FastAPI-сервер). В репозитории также есть **опциональный** FastAPI-прокси (профиль `api`) для API key / кастомных проверок здоровья / логирования.

---

## Требования

- Ubuntu 24.04 LTS
- NVIDIA Driver (под вашу версию CUDA) и доступная GPU `nvidia-smi`
- Docker + Docker Compose plugin
- NVIDIA Container Toolkit (замена `nvidia-docker2` на новых версиях)

---

## 1) Установка NVIDIA Container Toolkit (Ubuntu 24.04)

Если GPU уже работает (`nvidia-smi` на хосте показывает A5000), поставьте toolkit и перезапустите Docker:

Команды и актуальные инструкции: [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

Проверка, что Docker видит GPU:

```bash
docker run --rm --gpus all nvidia/cuda:12.6.1-base-ubuntu24.04 nvidia-smi
```

---

## 2) Конфигурация окружения

Файл `.env.example` в этом окружении заблокирован (dotfile), поэтому используем `env.example`.

Скопируйте и отредактируйте:

```bash
cp env.example .env
```

Поля:

- **`HF_TOKEN`**: токен Hugging Face (нужен для gated/private моделей)
- **`MODEL_NAME`**: Hugging Face repo id (например, `org/model-name`) или локальный путь `/data/models/...`
- **`SERVED_MODEL_NAME`**: любой удобный id (то, что будет в `/v1/models` и что вы указываете как `"model": "..."` в запросах)
- **`DTYPE=bfloat16`**, **`GPU_MEMORY_UTILIZATION=0.85`**, **`MAX_MODEL_LEN=8192`**, **`TENSOR_PARALLEL_SIZE=1`**

---

## 3) (Опционально) Скачать модель заранее в volume

Это ускорит первый старт и обеспечит повторное использование кэша.

```bash
chmod +x download_model.sh
HF_TOKEN=... ./download_model.sh org/model-name
```

После скачивания можно переключиться на локальный путь:

- **`MODEL_NAME=/data/models/<ИМЯ_ПАПКИ_ИЗ_СКРИПТА>`** (скрипт сам подскажет итоговый путь)

---

## 4) Запуск vLLM (OpenAI API) в Docker

```bash
docker compose up -d
```

Проверка логов:

```bash
docker compose logs -f vllm
```

Проверка утилизации GPU:

```bash
nvidia-smi
```

---

## 5) Проверка API

### cURL (без потока)

```bash
curl -s http://localhost:8000/v1/models | jq
```

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"local-model",
    "messages":[{"role":"user","content":"Привет! Коротко объясни, что такое vLLM."}],
    "max_tokens":128,
    "temperature":0.2
  }' | jq
```

### cURL (потоковая выдача SSE)

```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"local-model",
    "messages":[{"role":"user","content":"Напиши 3 пункта, почему streaming полезен."}],
    "max_tokens":128,
    "temperature":0.2,
    "stream": true
  }'
```

### Тест на Python

```bash
python3 -m pip install -r requirements.txt
python3 test_api.py
```

Если включили прокси (см. ниже) и задали `API_KEY`, то:

```bash
BASE_URL=http://localhost:8001 API_KEY=... python3 test_api.py
```

---

## 6) (Опционально) Запуск FastAPI-прокси (API key / кастомный /health)

Прокси слушает **`8001`** и проксирует на vLLM (`http://vllm:8000` внутри compose).

```bash
docker compose --profile api up -d --build
```

Если в `.env` задан `API_KEY`, то прокси будет требовать:

- `Authorization: Bearer <API_KEY>`

---

## Оптимизация под A5000 (24GB)

В `docker-compose.yml` уже выставлено:

- **`--dtype bfloat16`**: тип для уменьшения VRAM (обычно подходит для Ampere/A5000)
- **`--gpu-memory-utilization 0.85`**: оставляет запас под KV cache / пики
- **`--max-model-len 8192`**: разумный потолок контекста под 24GB
- **`--tensor-parallel-size 1`**: одна GPU

Если получите OOM:

- снизьте `GPU_MEMORY_UTILIZATION` до `0.80`
- снизьте `MAX_MODEL_LEN` до `6144` или `4096`

---

## Устранение неполадок

- **Container не видит GPU**:

  - проверьте `nvidia-smi` на хосте
  - проверьте `docker run --rm --gpus all ... nvidia-smi`
  - убедитесь, что установлен NVIDIA Container Toolkit и Docker перезапущен
- **Слишком долго стартует на первом запуске**:

  - это нормально, идёт скачивание модели/кэша
  - используйте `download_model.sh` заранее
- **Ошибки trust_remote_code**:

  - в compose уже включено `--trust-remote-code`
