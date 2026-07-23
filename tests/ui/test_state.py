from pptmaker.projects import ProjectCreate
from pptmaker.ui.state import initialize_session_state


def test_session_defaults_never_persist_api_key():
    state = {}

    initialize_session_state(state)

    assert state["api_key"] == ""
    assert "api_key" not in ProjectCreate(name="Demo").model_dump()


def test_streamlit_server_is_local_only():
    from pathlib import Path

    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")

    assert 'address = "127.0.0.1"' in config
