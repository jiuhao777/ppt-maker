import httpx
import openai

from pptmaker.providers import (
    OpenAICompatibleProvider,
    ProviderConfig,
)


CONFIG = ProviderConfig(
    provider_id="custom",
    base_url="https://test.invalid/v1",
    model="test-model",
)


class FakeCompletions:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return object()


class FakeClient:
    def __init__(self, completions):
        self.chat = type("Chat", (), {"completions": completions})()


def test_probe_reports_probed_and_unknown_capabilities():
    completions = FakeCompletions()
    provider = OpenAICompatibleProvider(
        CONFIG,
        client_factory=lambda **_kwargs: FakeClient(completions),
    )

    report = provider.probe("TEST_KEY")

    assert report.status == "success"
    assert report.capabilities["structured_output"].value is True
    assert report.capabilities["structured_output"].source == "probed"
    assert report.capabilities["tools"].value is True
    assert report.capabilities["vision"].value == "unknown"
    assert report.capabilities["max_context"].value == "unknown"
    assert "TEST_KEY" not in report.model_dump_json()


def test_probe_reports_unsupported_optional_capability():
    request = httpx.Request("POST", "https://test.invalid")
    response = httpx.Response(400, request=request)
    completions = FakeCompletions()

    def create(**kwargs):
        if "response_format" in kwargs:
            raise openai.BadRequestError("private", response=response, body=None)
        return object()

    completions.create = create
    provider = OpenAICompatibleProvider(
        CONFIG,
        client_factory=lambda **_kwargs: FakeClient(completions),
    )

    report = provider.probe("TEST_KEY")

    assert report.status == "success"
    assert report.capabilities["structured_output"].value is False
    assert report.capabilities["structured_output"].source == "probed"
    assert report.warnings


def test_probe_returns_safe_authentication_error():
    request = httpx.Request("POST", "https://test.invalid")
    response = httpx.Response(401, request=request)
    failure = openai.AuthenticationError("private", response=response, body=None)
    provider = OpenAICompatibleProvider(
        CONFIG,
        client_factory=lambda **_kwargs: FakeClient(FakeCompletions(failure)),
    )

    report = provider.probe("TEST_KEY")

    assert report.status == "failed"
    assert report.error.category == "authentication"
    assert "TEST_KEY" not in report.model_dump_json()
