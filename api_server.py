"""
Универсальный API-прокси для LLM backend'ов (vLLM, Ollama, llama.cpp).

Все три backend'а поддерживают OpenAI-совместимый API:
- vLLM: нативно
- Ollama: /v1/chat/completions (с версии 0.1.14+)
- llama.cpp: llama-server с --chat-template

Прокси автоматически определяет URL backend'а по переменной LLM_BACKEND,
либо использует явно заданный LLM_BACKEND_URL.
"""

import os
from typing import AsyncIterator, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

app = FastAPI(title="LLM Proxy", version="2.0.0")

# =============================================================================
# Конфигурация
# =============================================================================

# Маппинг backend'а на внутренний URL (внутри Docker network)
BACKEND_URLS = {
    "vllm": "http://llm-vllm:8000",
    "ollama": "http://llm-ollama:11434",
    "llamacpp": "http://llm-llamacpp:8080",
}

# Ollama использует другой путь для OpenAI-совместимого API
OLLAMA_OPENAI_PREFIX = "/v1"


def _get_llm_backend() -> str:
    """Возвращает выбранный backend (vllm, ollama, llamacpp)."""
    return os.getenv("LLM_BACKEND", "vllm").lower().strip()


def _get_backend_base_url() -> str:
    """
    Возвращает базовый URL backend'а.
    Приоритет: LLM_BACKEND_URL > автоопределение по LLM_BACKEND.
    """
    explicit_url = os.getenv("LLM_BACKEND_URL", "").strip()
    if explicit_url:
        return explicit_url.rstrip("/")

    backend = _get_llm_backend()
    return BACKEND_URLS.get(backend, BACKEND_URLS["vllm"])


def _get_api_key() -> str:
    """Возвращает API-ключ для авторизации (если задан)."""
    return os.getenv("API_KEY", "").strip()


def _get_served_model_name() -> str:
    """Возвращает имя модели для ответов /v1/models."""
    return os.getenv("SERVED_MODEL_NAME", "local-model").strip()


# =============================================================================
# Авторизация
# =============================================================================

def _auth_or_401(authorization: Optional[str]) -> None:
    """Проверяет Bearer-токен, если API_KEY задан."""
    expected = _get_api_key()
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Отсутствует Bearer-токен")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Неверный токен")


# =============================================================================
# Health check
# =============================================================================

@app.get("/health")
async def health() -> JSONResponse:
    """
    Проверка здоровья прокси.
    Для глубокой проверки можно добавить запрос к backend'у.
    """
    backend = _get_llm_backend()
    base_url = _get_backend_base_url()
    return JSONResponse({
        "status": "ok",
        "backend": backend,
        "backend_url": base_url,
    })


@app.get("/health/deep")
async def health_deep() -> JSONResponse:
    """
    Глубокая проверка: пингует backend.
    """
    backend = _get_llm_backend()
    base_url = _get_backend_base_url()

    # Определяем health endpoint для каждого backend'а
    health_paths = {
        "vllm": "/health",
        "ollama": "/api/tags",  # Ollama не имеет /health, но /api/tags работает
        "llamacpp": "/health",
    }
    health_path = health_paths.get(backend, "/health")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}{health_path}")
            backend_ok = resp.status_code == 200
    except Exception as e:
        return JSONResponse({
            "status": "unhealthy",
            "backend": backend,
            "backend_url": base_url,
            "error": str(e),
        }, status_code=503)

    return JSONResponse({
        "status": "ok" if backend_ok else "unhealthy",
        "backend": backend,
        "backend_url": base_url,
        "backend_status": resp.status_code,
    }, status_code=200 if backend_ok else 503)


# =============================================================================
# Прокси
# =============================================================================

async def _stream_bytes(resp: httpx.Response) -> AsyncIterator[bytes]:
    """Итератор для потоковой передачи байтов."""
    async for chunk in resp.aiter_bytes():
        if chunk:
            yield chunk


def _adjust_path_for_backend(path: str, backend: str) -> str:
    """
    Корректирует путь для разных backend'ов.
    Ollama и llama.cpp используют стандартные /v1/* пути.
    """
    # Все три backend'а поддерживают /v1/* пути
    return path


async def _proxy(request: Request, path: str, authorization: Optional[str]) -> Response:
    """Проксирует запрос к выбранному backend'у."""
    _auth_or_401(authorization)

    backend = _get_llm_backend()
    base_url = _get_backend_base_url()
    adjusted_path = _adjust_path_for_backend(path, backend)
    url = f"{base_url}{adjusted_path}"

    body = await request.body()
    headers = dict(request.headers)
    # Удаляем заголовки, которые httpx выставит сам
    headers.pop("host", None)
    headers.pop("content-length", None)

    timeout = httpx.Timeout(connect=10.0, read=None, write=30.0, pool=30.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.stream(
                request.method,
                url,
                content=body if body else None,
                headers=headers,
                params=request.query_params,
            )

            content_type = resp.headers.get("content-type", "application/json")
            status_code = resp.status_code

            # Потоковые ответы (SSE)
            if "text/event-stream" in content_type.lower():
                return StreamingResponse(
                    _stream_bytes(resp),
                    status_code=status_code,
                    media_type=content_type,
                )

            # Обычный ответ
            data = await resp.aread()
            return Response(content=data, status_code=status_code, media_type=content_type)

    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Не удалось подключиться к backend'у ({backend}): {e}"
        )
    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=504,
            detail=f"Таймаут при обращении к backend'у ({backend}): {e}"
        )


# =============================================================================
# OpenAI-совместимые эндпоинты
# =============================================================================

@app.api_route("/v1/chat/completions", methods=["POST"])
async def chat_completions(
    request: Request,
    authorization: Optional[str] = Header(default=None)
) -> Response:
    """Проксирует chat completions запросы."""
    return await _proxy(request, "/v1/chat/completions", authorization)


@app.api_route("/v1/completions", methods=["POST"])
async def completions(
    request: Request,
    authorization: Optional[str] = Header(default=None)
) -> Response:
    """Проксирует completions запросы (legacy)."""
    return await _proxy(request, "/v1/completions", authorization)


@app.api_route("/v1/models", methods=["GET"])
async def models(
    request: Request,
    authorization: Optional[str] = Header(default=None)
) -> Response:
    """Проксирует запрос списка моделей."""
    return await _proxy(request, "/v1/models", authorization)


@app.api_route("/v1/embeddings", methods=["POST"])
async def embeddings(
    request: Request,
    authorization: Optional[str] = Header(default=None)
) -> Response:
    """Проксирует embeddings запросы (если backend поддерживает)."""
    return await _proxy(request, "/v1/embeddings", authorization)


# =============================================================================
# Информация о конфигурации
# =============================================================================

@app.get("/config")
async def config() -> JSONResponse:
    """Возвращает текущую конфигурацию прокси (без секретов)."""
    return JSONResponse({
        "backend": _get_llm_backend(),
        "backend_url": _get_backend_base_url(),
        "served_model_name": _get_served_model_name(),
        "auth_enabled": bool(_get_api_key()),
    })
