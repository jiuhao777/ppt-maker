from collections.abc import MutableMapping

from pptmaker.providers import PRESETS


def initialize_session_state(state: MutableMapping) -> None:
    default = PRESETS["deepseek"]
    state.setdefault("api_key", "")
    state.setdefault("bocha_api_key", "")
    state.setdefault("bocha_connection_verified", False)
    state.setdefault("show_search_settings", False)
    state.setdefault("search_freshness", "oneYear")
    state.setdefault("provider_id", "deepseek")
    state.setdefault("provider_base_url", default.base_url)
    state.setdefault("provider_model", default.model)
    state.setdefault("selected_project_id", None)
    state.setdefault("startup_reconciled", False)
