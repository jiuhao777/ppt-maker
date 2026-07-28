from typing import Any

import httpx


class DeepSeekRequestError(RuntimeError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"DeepSeek request failed with HTTP {status_code}")


def deepseek_chat(
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    response_format: dict | None = None,
    max_tokens: int = 8192,
    tools: list[dict] | None = None,
    tool_choice: dict | None = None,
) -> dict:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
    }
    if response_format is not None:
        payload["response_format"] = response_format
    if tools is not None:
        payload["tools"] = tools
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    response = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        raise DeepSeekRequestError(response.status_code)
    return response.json()
