#!/usr/bin/env python3
"""
Тестовый скрипт для проверки LLM API.
Работает с любым backend'ом (vLLM, Ollama, llama.cpp).

Использование:
    python test_api.py

Переменные окружения:
    BASE_URL      - URL API (по умолчанию определяется по LLM_BACKEND)
    LLM_BACKEND   - backend (vllm, ollama, llamacpp) — влияет на BASE_URL
    MODEL         - имя модели (если не задано — определяется автоматически)
    API_KEY       - API ключ (опционально)
"""

import json
import os
import sys
import time

import requests


# URL по умолчанию для каждого backend'а
DEFAULT_URLS = {
    "vllm": "http://localhost:8000",
    "ollama": "http://localhost:8000",  # Порт проброшен в compose: 8000:11434
    "llamacpp": "http://localhost:8000",  # Порт проброшен в compose: 8000:8080
}


def get_base_url() -> str:
    """Определяет BASE_URL по переменным окружения."""
    explicit = os.getenv("BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")

    backend = os.getenv("LLM_BACKEND", "vllm").lower().strip()
    return DEFAULT_URLS.get(backend, DEFAULT_URLS["vllm"])


def sse_stream(resp: requests.Response):
    """Генератор для парсинга SSE-потока."""
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data: "):
            payload = line.removeprefix("data: ").strip()
            if payload == "[DONE]":
                return
            yield payload


def main() -> int:
    base_url = get_base_url()
    model = os.getenv("MODEL", "").strip()
    api_key = os.getenv("API_KEY", "").strip()
    backend = os.getenv("LLM_BACKEND", "vllm").lower().strip()

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    print("=" * 50)
    print(f"Backend:     {backend}")
    print(f"Базовый URL: {base_url}")
    print("=" * 50)

    # =========================================================================
    # Проверка /health
    # =========================================================================
    print("\n[1] Проверка /health")
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        print(f"    GET /health: {r.status_code}")
        if r.status_code == 200:
            print(f"    Ответ: {r.text[:200]}")
    except requests.exceptions.ConnectionError:
        print("    /health недоступен (это нормально для некоторых backend'ов)")
    except Exception as e:
        print(f"    Ошибка: {e}")

    # =========================================================================
    # Список моделей
    # =========================================================================
    print("\n[2] Получение списка моделей")
    try:
        r = requests.get(f"{base_url}/v1/models", headers=headers, timeout=30)
        print(f"    GET /v1/models: {r.status_code}")

        if r.status_code != 200:
            print(f"    Ошибка: {r.text}")
            return 1

        models_data = r.json()
        available_models = models_data.get("data", [])

        if available_models:
            print(f"    Доступные модели: {[m.get('id', m) for m in available_models]}")

            # Автоопределение модели
            if not model:
                model = available_models[0].get("id", "")
                print(f"    Автовыбор модели: {model}")
        else:
            print("    Моделей не найдено в ответе")

    except Exception as e:
        print(f"    Ошибка при получении моделей: {e}")
        return 1

    if not model:
        print("\n    Не удалось определить модель. Укажите переменную MODEL.")
        return 1

    # =========================================================================
    # Chat completions (без потока)
    # =========================================================================
    print(f"\n[3] Chat completions (без потока), модель: {model}")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Ты полезный ассистент. Отвечай кратко."},
            {"role": "user", "content": "Скажи «пинг» и кратко объясни, кто ты."},
        ],
        "temperature": 0.2,
        "max_tokens": 128,
        "stream": False,
    }

    try:
        t0 = time.time()
        r = requests.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=300,
        )
        dt = time.time() - t0

        print(f"    POST /v1/chat/completions: {r.status_code} ({dt:.2f}s)")

        if r.status_code != 200:
            print(f"    Ошибка: {r.text}")
            return 1

        response_data = r.json()
        content = response_data["choices"][0]["message"]["content"]
        print(f"    Ответ: {content}")

        # Статистика использования (если есть)
        usage = response_data.get("usage", {})
        if usage:
            print(f"    Токены: prompt={usage.get('prompt_tokens', '?')}, "
                  f"completion={usage.get('completion_tokens', '?')}, "
                  f"total={usage.get('total_tokens', '?')}")

    except Exception as e:
        print(f"    Ошибка: {e}")
        return 1

    # =========================================================================
    # Chat completions (с потоком SSE)
    # =========================================================================
    print(f"\n[4] Chat completions (поток SSE), модель: {model}")

    payload["stream"] = True
    payload["messages"][1]["content"] = "Напиши 3 коротких пункта о себе."

    try:
        print("    Потоковый ответ: ", end="", flush=True)

        with requests.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            stream=True,
            timeout=300,
        ) as r:
            if r.status_code != 200:
                print(f"\n    Ошибка: {r.status_code} {r.text}")
                return 1

            collected = []
            for data in sse_stream(r):
                try:
                    obj = json.loads(data)
                    delta = obj["choices"][0].get("delta", {}).get("content", "")
                    if delta:
                        sys.stdout.write(delta)
                        sys.stdout.flush()
                        collected.append(delta)
                except json.JSONDecodeError:
                    # Иногда приходят неполные JSON — игнорируем
                    pass

        print()  # Новая строка после потока

    except Exception as e:
        print(f"\n    Ошибка: {e}")
        return 1

    # =========================================================================
    # Итог
    # =========================================================================
    print("\n" + "=" * 50)
    print("Все проверки пройдены успешно!")
    print("=" * 50)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
