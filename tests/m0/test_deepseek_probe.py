from collections import deque

import pytest
from pydantic import ValidationError

from pptmaker.m0 import deepseek_probe
from pptmaker.m0.contracts import ProbeResult, ProbeStatus
from pptmaker.m0.deepseek_probe import (
    _safe_error_signature,
    parse_outline,
    run_structured_probe,
)


VALID = '{"title":"项目汇报","slides":["背景","方案","结果"]}'


def test_error_signature_redacts_api_keys():
    assert "secret" not in _safe_error_signature(
        ValueError("invalid sk-secret")
    )


def test_error_signature_keeps_safe_provider_hint():
    error = ValueError("Error code: 400")
    error.body = {
        "code": "invalid_parameter",
        "message": "model is unavailable",
        "param": "model",
        "api_key": "sk-secret",
    }
    signature = _safe_error_signature(error)
    assert "invalid_parameter" in signature
    assert '"param": "model"' in signature
    assert "sk-secret" not in signature


def test_parses_valid_outline():
    value = parse_outline(VALID)
    assert value.slides == ["背景", "方案", "结果"]


def test_rejects_too_short_outline():
    with pytest.raises(ValidationError):
        parse_outline('{"title":"项目汇报","slides":["背景"]}')


def test_rejects_markdown_fenced_json_on_first_pass():
    with pytest.raises(ValidationError):
        parse_outline(f"```json\n{VALID}\n```")


def test_twenty_trials_allow_exactly_one_repair_and_meet_gate():
    responses = deque([(VALID, 10, 5)] * 19 + [("not-json", 10, 1), (VALID, 8, 5)])
    calls = []

    def requester(messages):
        calls.append(messages)
        return responses.popleft()

    result = run_structured_probe(requester, iterations=20)

    assert result.status.value == "pass"
    assert result.metrics["first_pass_rate"] == 0.95
    assert result.metrics["repaired_pass_rate"] == 1.0
    assert result.metrics["repair_requests"] == 1
    assert len(calls) == 21


def test_failed_single_repair_fails_gate_without_retrying_again():
    responses = deque([(VALID, 10, 5)] * 19 + [("bad", 10, 1), ("still-bad", 8, 1)])

    result = run_structured_probe(lambda _messages: responses.popleft(), iterations=20)

    assert result.status.value == "fail"
    assert result.metrics["repair_requests"] == 1
    assert result.metrics["repaired_pass_rate"] == 0.95


def test_module_entrypoint_writes_machine_readable_result(monkeypatch, tmp_path):
    monkeypatch.setattr(
        deepseek_probe,
        "run_online_probe",
        lambda: ProbeResult(
            name="deepseek-structured-output",
            status=ProbeStatus.PASS,
        ),
    )

    path = deepseek_probe.main(tmp_path)

    assert path == tmp_path / "artifacts" / "m0" / "deepseek-structured-output.json"
    assert '"status": "pass"' in path.read_text("utf-8")


def test_online_request_uses_current_non_thinking_model(monkeypatch):
    calls = []

    def request(key, base_url, model, messages, **kwargs):
        calls.append((key, base_url, model, messages, kwargs))
        return {
            "choices": [{"message": {"content": VALID}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

    monkeypatch.setattr(deepseek_probe, "deepseek_chat", request)
    result = deepseek_probe._online_requester(
        "TEST_KEY",
        "https://api.deepseek.com",
        "deepseek-v4-pro",
    )(deepseek_probe.BASE_MESSAGES)

    assert result == (VALID, 10, 5)
    assert calls[0][2] == "deepseek-v4-pro"
    assert calls[0][4]["response_format"] == {"type": "json_object"}
    assert calls[0][4]["max_tokens"] == 512
