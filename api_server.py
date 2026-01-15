import os
from typing import AsyncIterator, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

app = FastAPI(title="Qwen3 vLLM Proxy", version="1.0.0")


def _get_vllm_base_url() -> str:
    return os.getenv("VLLM_BASE_URL", "http://localhost:8000").rstrip("/")


def _get_api_key() -> str:
    return os.getenv("API_KEY", "").strip()


def _auth_or_401(authorization: Optional[str]) -> None:
    expected = _get_api_key()
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Отсутствует Bearer-токен")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Неверный токен")


@app.get("/health")
async def health() -> JSONResponse:
    # "Поверхностная" проверка: прокси жив. Для "глубокой" проверки можно дернуть vLLM.
    return JSONResponse({"status": "ok"})


async def _stream_bytes(resp: httpx.Response) -> AsyncIterator[bytes]:
    async for chunk in resp.aiter_bytes():
        if chunk:
            yield chunk


async def _proxy(request: Request, path: str, authorization: Optional[str]) -> Response:
    _auth_or_401(authorization)

    base = _get_vllm_base_url()
    url = f"{base}{path}"

    body = await request.body()
    headers = dict(request.headers)
    # Пусть httpx сам корректно выставит Host/content-length
    headers.pop("host", None)
    headers.pop("content-length", None)

    timeout = httpx.Timeout(connect=10.0, read=None, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        upstream = await client.stream(
            request.method,
            url,
            content=body if body else None,
            headers=headers,
            params=request.query_params,
        )

        content_type = upstream.headers.get("content-type", "application/json")
        status_code = upstream.status_code

        # Потоковые ответы (SSE) и любые chunked-ответы
        if "text/event-stream" in content_type.lower():
            return StreamingResponse(
                _stream_bytes(upstream),
                status_code=status_code,
                media_type=content_type,
            )

        # Обычный (не потоковый) ответ
        data = await upstream.aread()
        return Response(content=data, status_code=status_code, media_type=content_type)


@app.api_route("/v1/chat/completions", methods=["POST"])
async def chat_completions(request: Request, authorization: Optional[str] = Header(default=None)) -> Response:
    return await _proxy(request, "/v1/chat/completions", authorization)


@app.api_route("/v1/models", methods=["GET"])
async def models(request: Request, authorization: Optional[str] = Header(default=None)) -> Response:
    return await _proxy(request, "/v1/models", authorization)


@app.api_route("/v1/completions", methods=["POST"])
async def completions(request: Request, authorization: Optional[str] = Header(default=None)) -> Response:
    return await _proxy(request, "/v1/completions", authorization)

