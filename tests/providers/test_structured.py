from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from pptmaker.providers.models import ProviderConfig
from pptmaker.providers.structured import StructuredModel, StructuredOutputError


CONFIG = ProviderConfig(
    provider_id="test",
    base_url="https://test.invalid/v1",
    model="test-model",
)


class Answer(BaseModel):
    value: str


class FakeCompletions:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def create(self, **arguments):
        self.calls.append(arguments)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        message = SimpleNamespace(content=result)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeFactory:
    def __init__(self, results):
        self.completions = FakeCompletions(results)
        self.chat = SimpleNamespace(completions=self.completions)
        self.received_key = None

    def __call__(self, *, api_key, base_url):
        self.received_key = api_key
        return self


def test_valid_json_needs_one_request():
    client = FakeFactory(['{"value":"ok"}'])

    result = StructuredModel(CONFIG, client).generate(
        Answer,
        "system",
        "user",
        "TEST_KEY",
    )

    assert result.value == "ok"
    assert len(client.completions.calls) == 1


def test_invalid_json_gets_exactly_one_repair():
    client = FakeFactory(["not json", '{"value":"fixed"}', '{"value":"ignored"}'])

    result = StructuredModel(CONFIG, client).generate(
        Answer,
        "system",
        "user",
        "TEST_KEY",
    )

    assert result.value == "fixed"
    assert len(client.completions.calls) == 2
    assert "修复" in client.completions.calls[1]["messages"][-1]["content"]


def test_second_invalid_result_returns_safe_error():
    client = FakeFactory(["not json", '{"wrong":"shape"}', '{"still":"bad"}'])

    with pytest.raises(StructuredOutputError) as error:
        StructuredModel(CONFIG, client).generate(
            Answer,
            "system",
            "user",
            "TEST_KEY",
        )

    assert error.value.category == "invalid_structure"
    assert "TEST_KEY" not in str(error.value)
    assert len(client.completions.calls) == 3


def test_invalid_model_content_is_not_exposed():
    secret = "private material sk-123456"
    client = FakeFactory([secret, secret, secret])

    with pytest.raises(StructuredOutputError) as error:
        StructuredModel(CONFIG, client).generate(
            Answer,
            "system",
            "user",
            "TEST_KEY",
        )

    assert secret not in str(error.value)
    assert "sk-" not in str(error.value)


def test_empty_response_gets_one_repair():
    client = FakeFactory(["", '{"value":"fixed"}', '{"value":"ignored"}'])

    result = StructuredModel(CONFIG, client).generate(
        Answer,
        "system",
        "user",
        "TEST_KEY",
    )

    assert result.value == "fixed"
    assert len(client.completions.calls) == 2


def test_provider_failure_returns_only_safe_category():
    client = FakeFactory([RuntimeError("https://private key=TEST_KEY body=secret")])

    with pytest.raises(StructuredOutputError) as error:
        StructuredModel(CONFIG, client).generate(
            Answer,
            "system",
            "user",
            "TEST_KEY",
        )

    assert error.value.category == "unknown"
    assert "TEST_KEY" not in str(error.value)
    assert "https://" not in str(error.value)


def test_deepseek_structured_request_uses_direct_http(monkeypatch):
    calls = []

    def request(*args, **kwargs):
        calls.append((args, kwargs))
        return {"choices": [{"message": {"content": '{"value":"ok"}'}}]}

    monkeypatch.setattr(
        "pptmaker.providers.structured.deepseek_chat",
        request,
    )
    client = FakeFactory([])
    config = CONFIG.model_copy(update={"provider_id": "deepseek"})

    result = StructuredModel(config, client).generate(
        Answer, "system", "user", "TEST_KEY"
    )

    assert result.value == "ok"
    assert calls[0][0][0] == "TEST_KEY"
    assert calls[0][1]["response_format"] == {"type": "json_object"}
    assert client.completions.calls == []
