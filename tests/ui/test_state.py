from pptmaker.projects import ProjectCreate
from pptmaker.ui.state import initialize_session_state


def test_session_defaults_never_persist_api_key():
    state = {}

    initialize_session_state(state)

    assert state["api_key"] == ""
    assert "api_key" not in ProjectCreate(name="Demo").model_dump()
