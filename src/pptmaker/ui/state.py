from collections.abc import MutableMapping

from pptmaker.providers import PRESETS
from pptmaker.providers.structured import StructuredOutputError


SAFE_PROVIDER_MESSAGES = {
    "authentication": "API Key 无效或无权访问该模型。",
    "rate_limit": "模型服务请求过于频繁，请稍后重试。",
    "timeout": "模型服务响应超时，请重试。",
    "invalid_structure": "模型未返回有效结构化结果，请重试。",
}


def safe_generation_message(exc: Exception) -> str:
    if isinstance(exc, StructuredOutputError):
        return SAFE_PROVIDER_MESSAGES.get(
            exc.category,
            "模型服务暂时不可用。",
        )
    return "生成失败，请重试。"


def initialize_session_state(state: MutableMapping) -> None:
    default = PRESETS["deepseek"]
    state.setdefault("api_key", "")
    state.setdefault("bocha_api_key", "")
    state.setdefault("bocha_connection_verified", False)
    state.setdefault("show_search_settings", False)
    state.setdefault("provider_id", "deepseek")
    state.setdefault("provider_base_url", default.base_url)
    state.setdefault("provider_model", default.model)
    state.setdefault("selected_project_id", None)
    state.setdefault("startup_reconciled", False)
