# Локальный LLM-сервис с переключаемым backend'ом

Развёртывание LLM на GPU с **переключением между тремя backend'ами**:
- **vLLM** — высокая производительность, оптимизации под GPU
- **Ollama** — простота использования, встроенный менеджер моделей
- **llama.cpp** — максимальная гибкость, GGUF-квантизации

Все backend'ы предоставляют **OpenAI-совместимый API**:
- `POST /v1/chat/completions` (с поддержкой streaming SSE)
- `GET /v1/models`
- `GET /health`

---

## Требования

- Ubuntu 24.04 LTS (или другой Linux с NVIDIA GPU)
- NVIDIA Driver + CUDA
- Docker + Docker Compose (с поддержкой GPU)
- NVIDIA Container Toolkit

### Проверка GPU в Docker

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu24.04 nvidia-smi
```

---

## Быстрый старт

### 1) Конфигурация

```bash
cp env.example .env
```

Отредактируйте `.env` и выберите backend:

```bash
# Варианты: vllm, ollama, llamacpp
LLM_BACKEND=vllm
```

### 2) Скачивание модели

Выберите скрипт в зависимости от backend'а:

```bash
# Сделать скрипты исполняемыми
chmod +x scripts/*.sh

# vLLM (Hugging Face модели)
./scripts/download_model_vllm.sh Qwen/Qwen3-8B-AWQ

# Ollama
./scripts/pull_model_ollama.sh qwen3:8b

# llama.cpp (GGUF)
./scripts/download_model_llamacpp.sh Qwen/Qwen3-8B-GGUF qwen3-8b-q4_k_m.gguf
```

### 3) Запуск

```bash
# vLLM
docker compose --profile vllm up -d

# Ollama
docker compose --profile ollama up -d

# llama.cpp
docker compose --profile llamacpp up -d
```

### 4) Проверка

```bash
# Health check
curl http://localhost:8000/health

# Список моделей
curl http://localhost:8000/v1/models

# Тестовый запрос
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-8b",
    "messages": [{"role": "user", "content": "Привет!"}],
    "max_tokens": 100
  }'
```

---

## Конфигурация backend'ов

### vLLM

Переменные в `.env`:

| Переменная | Описание | Пример |
|------------|----------|--------|
| `VLLM_MODEL` | HF repo id модели | `Qwen/Qwen3-8B-AWQ` |
| `VLLM_QUANTIZATION` | Тип квантизации | `awq`, `gptq`, пусто |
| `VLLM_GPU_MEM_UTIL` | Использование GPU памяти | `0.65` |
| `VLLM_KV_CACHE_DTYPE` | Тип KV cache | `fp8`, `auto` |
| `MAX_MODEL_LEN` | Макс. длина контекста | `8192` |

### Ollama

Переменные в `.env`:

| Переменная | Описание | Пример |
|------------|----------|--------|
| `OLLAMA_MODEL` | Имя модели в Ollama | `qwen3:8b` |
| `OLLAMA_MODELS_DIR` | Путь к моделям | `./data/ollama` |
| `OLLAMA_NUM_PARALLEL` | Параллельные запросы | `2` |

Доступные модели Qwen3 в Ollama:
- `qwen3:8b` — 8B параметров
- `qwen3:14b` — 14B параметров  
- `qwen3:32b` — 32B параметров

### llama.cpp

Переменные в `.env`:

| Переменная | Описание | Пример |
|------------|----------|--------|
| `LLAMACPP_MODEL_FILE` | Имя GGUF-файла | `qwen3-8b-q4_k_m.gguf` |
| `LLAMACPP_MODELS_DIR` | Путь к моделям | `./data/llamacpp` |
| `LLAMACPP_GPU_LAYERS` | Слоёв на GPU | `99` (все) |
| `LLAMACPP_CHAT_TEMPLATE` | Шаблон чата | `qwen3` |

Рекомендуемые GGUF-квантизации:
- `Q4_K_M` — баланс качества и скорости
- `Q5_K_M` — выше качество
- `Q8_0` — максимальное качество

---

## Дополнительные сервисы

Кроме LLM, compose поднимает:

| Сервис | Порт | Описание |
|--------|------|----------|
| **Embedding** | 8001 | Векторные представления (vLLM) |
| **Reranker** | 8002 | Переранжирование (vLLM) |

Эти сервисы запускаются **всегда**, независимо от выбранного LLM backend'а.

---

## API Proxy (опционально)

Для унификации доступа к любому backend'у можно использовать FastAPI-прокси:

```bash
# Запуск прокси вместе с выбранным backend'ом
docker compose --profile vllm --profile api up -d
```

Прокси будет доступен на порту **8080** и автоматически направит запросы к нужному backend'у.

Поддерживает:
- Авторизацию через `API_KEY`
- Deep health check (`/health/deep`)
- Информацию о конфигурации (`/config`)

---

## Переключение между backend'ами

### Остановить текущий и запустить другой

```bash
# Остановить всё
docker compose --profile vllm --profile ollama --profile llamacpp down

# Запустить нужный
docker compose --profile ollama up -d
```

### Изменить через .env

1. Остановите сервисы: `docker compose down`
2. Измените `LLM_BACKEND` в `.env`
3. Запустите нужный профиль

---

## Тестирование

### Python-тест

```bash
pip install -r requirements.txt
python test_api.py
```

Скрипт автоматически определит модель из `/v1/models`.

### Streaming (SSE)

```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-8b",
    "messages": [{"role": "user", "content": "Напиши короткую историю"}],
    "max_tokens": 200,
    "stream": true
  }'
```

---

## Мониторинг

### Логи

```bash
# vLLM
docker compose logs -f llm-vllm

# Ollama
docker compose logs -f llm-ollama

# llama.cpp
docker compose logs -f llm-llamacpp
```

### GPU

```bash
nvidia-smi
watch -n 1 nvidia-smi
```

---

## Устранение неполадок

### Container не видит GPU

```bash
# Проверить драйвер
nvidia-smi

# Проверить Docker + GPU
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu24.04 nvidia-smi

# Если не работает — установить NVIDIA Container Toolkit
```

### Out of Memory (OOM)

- Уменьшите `VLLM_GPU_MEM_UTIL` (например, до `0.5`)
- Уменьшите `MAX_MODEL_LEN` (например, до `4096`)
- Используйте квантизированную модель (AWQ, GPTQ, GGUF Q4)

### Ollama не видит модель

```bash
# Проверить скачанные модели
docker exec llm-ollama ollama list

# Скачать модель вручную
docker exec llm-ollama ollama pull qwen3:8b
```

### llama.cpp не находит модель

- Проверьте, что файл `.gguf` лежит в `LLAMACPP_MODELS_DIR`
- Проверьте, что `LLAMACPP_MODEL_FILE` указывает на правильное имя файла

---

## Структура проекта

```
.
├── docker-compose.yml      # Все сервисы с профилями
├── Dockerfile              # Образ для API-прокси
├── api_server.py           # FastAPI-прокси
├── env.example             # Шаблон конфигурации
├── requirements.txt        # Python-зависимости
├── test_api.py             # Тестовый скрипт
├── scripts/
│   ├── download_model_vllm.sh      # Скачивание для vLLM
│   ├── pull_model_ollama.sh        # Скачивание для Ollama
│   └── download_model_llamacpp.sh  # Скачивание для llama.cpp
└── data/
    ├── ollama/             # Модели Ollama
    └── llamacpp/           # GGUF-модели
```
