import json
import os
import sys
import time

import requests


def sse_stream(resp: requests.Response):
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data: "):
            payload = line.removeprefix("data: ").strip()
            if payload == "[DONE]":
                return
            yield payload


def main() -> int:
    base_url = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
    model = os.getenv("MODEL", "qwen3-8b")
    api_key = os.getenv("API_KEY", "").strip()

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    print(f"Base URL: {base_url}")

    # Health
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        print("GET /health:", r.status_code, r.text[:200])
    except Exception as e:
        print("GET /health failed:", e)

    # Models
    r = requests.get(f"{base_url}/v1/models", headers=headers, timeout=30)
    print("GET /v1/models:", r.status_code)
    if r.status_code != 200:
        print(r.text)
        return 1

    # Non-streaming chat
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'ping' and then explain in 1 sentence what you are."},
        ],
        "temperature": 0.2,
        "max_tokens": 128,
        "stream": False,
    }
    t0 = time.time()
    r = requests.post(f"{base_url}/v1/chat/completions", headers=headers, data=json.dumps(payload), timeout=300)
    dt = time.time() - t0
    print("POST /v1/chat/completions (non-stream):", r.status_code, f"{dt:.2f}s")
    if r.status_code != 200:
        print(r.text)
        return 1
    print("Assistant:", r.json()["choices"][0]["message"]["content"])

    # Streaming chat
    payload["stream"] = True
    print("\nStreaming response:")
    with requests.post(
        f"{base_url}/v1/chat/completions",
        headers=headers,
        data=json.dumps(payload),
        stream=True,
        timeout=300,
    ) as r:
        print("POST /v1/chat/completions (stream):", r.status_code)
        if r.status_code != 200:
            print(r.text)
            return 1
        for data in sse_stream(r):
            try:
                obj = json.loads(data)
                delta = obj["choices"][0].get("delta", {}).get("content", "")
                if delta:
                    sys.stdout.write(delta)
                    sys.stdout.flush()
            except Exception:
                # Sometimes you may see keep-alives or partial lines; ignore
                pass
    print("\n\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

