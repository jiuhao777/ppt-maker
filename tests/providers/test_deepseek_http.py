import httpx
import pytest

from pptmaker.providers.deepseek_http import (
    DeepSeekRequestError,
    deepseek_chat,
)


def test_deepseek_http_disables_thinking_and_keeps_key_in_header(
    monkeypatch,
):
    captured = {}

    def post(url, *, headers, json, timeout):
        captured.update(
            url=url,
            headers=headers,
            payload=json,
            timeout=timeout,
        )
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": "{}"}}]},
        )

    monkeypatch.setattr(httpx, "post", post)
    deepseek_chat(
        "TEST_KEY",
        "https://api.deepseek.com",
        "deepseek-v4-pro",
        [{"role": "user", "content": "JSON"}],
        response_format={"type": "json_object"},
    )

    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert captured["headers"]["Authorization"] == "Bearer TEST_KEY"
    assert "TEST_KEY" not in str(captured["payload"])


def test_deepseek_http_raises_status_only(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kwargs: httpx.Response(
            400,
            request=httpx.Request("POST", url),
            text="private response",
        ),
    )
    with pytest.raises(DeepSeekRequestError, match="HTTP 400"):
        deepseek_chat(
            "TEST_KEY",
            "https://api.deepseek.com",
            "deepseek-v4-pro",
            [{"role": "user", "content": "test"}],
        )
