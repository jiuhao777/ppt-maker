from pptmaker.projects import ProjectCreate
from pptmaker.providers.structured import StructuredOutputError
from pptmaker.ui.state import initialize_session_state, safe_generation_message


def test_session_defaults_never_persist_api_key():
    state = {}

    initialize_session_state(state)

    assert state["api_key"] == ""
    assert state["bocha_api_key"] == ""
    assert state["bocha_connection_verified"] is False
    assert "api_key" not in ProjectCreate(name="Demo").model_dump()
    assert "bocha_api_key" not in ProjectCreate(name="Demo").model_dump()


def test_streamlit_server_is_local_only():
    from pathlib import Path

    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")

    assert 'address = "127.0.0.1"' in config


def test_generation_error_message_never_uses_raw_exception_text():
    provider_error = StructuredOutputError(
        "authentication",
        "https://private.invalid sk-123456",
    )

    assert safe_generation_message(provider_error) == "API Key 无效或无权访问该模型。"
    assert safe_generation_message(
        RuntimeError("C:\\private\\project sk-123456")
    ) == "生成失败，请重试。"
