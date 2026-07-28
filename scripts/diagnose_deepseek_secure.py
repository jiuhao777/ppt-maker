import getpass
import json
import re

import httpx


URL = "https://api.deepseek.com/chat/completions"


def _redact(value: str) -> str:
    value = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-<redacted>", value)
    return re.sub(
        r"(?i)(authorization|api[_-]?key|bearer)(\s*[:=]?\s*)\S+",
        r"\1\2<redacted>",
        value,
    )


def _request(key: str, model: str, *, json_mode: bool) -> tuple[int, str]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    'Return JSON exactly like {"ok":true}.'
                    if json_mode
                    else "Reply with OK."
                ),
            },
            {"role": "user", "content": "Test."},
        ],
        "max_tokens": 32,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    response = httpx.post(
        URL,
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
        timeout=30,
    )
    try:
        body = json.dumps(response.json(), ensure_ascii=False)
    except ValueError:
        body = response.text
    return response.status_code, _redact(body[:1000])


def run() -> int:
    key = getpass.getpass("DeepSeek API key (hidden): ").strip()
    if not key:
        raise SystemExit("DeepSeek API key is required")
    try:
        checks = [
            ("v4-pro plain", "deepseek-v4-pro", False),
            ("v4-flash plain", "deepseek-v4-flash", False),
            ("v4-pro JSON", "deepseek-v4-pro", True),
        ]
        for label, model, json_mode in checks:
            try:
                status, body = _request(
                    key, model, json_mode=json_mode
                )
            except httpx.HTTPError as exc:
                print(f"{label}: network_error {type(exc).__name__}")
            else:
                print(f"{label}: HTTP {status}")
                print(body)
    finally:
        key = ""
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
