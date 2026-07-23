import logging

import httpx
import openai
import pytest

from pptmaker.logging_config import configure_logging
from pptmaker.security.secrets import redact_text, safe_provider_error


@pytest.mark.parametrize(
    "value",
    [
        "Authorization: Bearer TEST_KEY",
        "Bearer TEST_KEY",
        "api_key=TEST_KEY",
        "token sk-TESTVALUE123",
    ],
)
def test_log_filter_removes_secrets(value, caplog):
    configure_logging()

    logging.getLogger("pptmaker.test").warning("%s", value)

    assert "TEST_KEY" not in caplog.text
    assert "sk-TESTVALUE123" not in caplog.text


def test_redaction_handles_message_and_mapping_values():
    assert "TEST_KEY" not in redact_text(
        "request headers={'Authorization': 'Bearer TEST_KEY'}"
    )
    assert "TEST_KEY" not in redact_text("{'api_key': 'TEST_KEY'}")


def test_log_filter_redacts_secret_dictionary_values(caplog):
    configure_logging()

    logging.getLogger("pptmaker.test").warning(
        "config=%s", {"api_key": "TEST_KEY"}
    )

    assert "TEST_KEY" not in caplog.text


def _response(status):
    request = httpx.Request("POST", "https://test.invalid")
    return httpx.Response(status, request=request)


@pytest.mark.parametrize(
    ("exception", "category"),
    [
        (
            openai.AuthenticationError(
                "private", response=_response(401), body=None
            ),
            "authentication",
        ),
        (
            openai.RateLimitError("private", response=_response(429), body=None),
            "rate_limit",
        ),
        (
            openai.APITimeoutError(
                request=httpx.Request("POST", "https://test.invalid")
            ),
            "timeout",
        ),
        (
            openai.APIConnectionError(
                request=httpx.Request("POST", "https://test.invalid")
            ),
            "network",
        ),
        (
            openai.BadRequestError(
                "private", response=_response(400), body=None
            ),
            "unsupported",
        ),
        (RuntimeError("https://host key=TEST_KEY body=private"), "unknown"),
    ],
)
def test_provider_errors_use_fixed_safe_categories(exception, category):
    result = safe_provider_error(exception)

    assert result.category == category
    assert "private" not in result.message
    assert "TEST_KEY" not in result.message
    assert "https://" not in result.message


def test_dependency_log_levels_are_not_debug():
    configure_logging()

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    assert logging.getLogger("openai").level == logging.WARNING
