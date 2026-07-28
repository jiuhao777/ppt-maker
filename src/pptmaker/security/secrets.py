import re

import openai
from pydantic import BaseModel


_PATTERNS = (
    re.compile(
        r"(?i)(['\"]?authorization['\"]?\s*[:=]\s*['\"]?)"
        r"(?:bearer\s+)?[^\s,;'\"}]+"
    ),
    re.compile(r"(?i)(bearer\s+)[^\s,;'\"}]+"),
    re.compile(
        r"(?i)(['\"]?api[_-]?key['\"]?\s*[:=]\s*['\"]?)"
        r"[^\s,;'\"}]+"
    ),
    re.compile(r"(?i)\bsk-[A-Za-z0-9_-]+"),
)


class ProviderError(BaseModel):
    category: str
    message: str


def redact_text(value: str) -> str:
    redacted = value
    for pattern in _PATTERNS:
        redacted = pattern.sub(
            lambda match: (
                f"{match.group(1)}[REDACTED]"
                if match.lastindex
                else "[REDACTED]"
            ),
            redacted,
        )
    return redacted


def _redact_value(value):
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in {"api_key", "apikey", "authorization"}:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_value(item)
        return redacted
    return value


def safe_provider_error(exc: Exception) -> ProviderError:
    status_code = getattr(exc, "status_code", None)
    if isinstance(exc, openai.AuthenticationError) or status_code == 401:
        category = "authentication"
        message = "API Key 无效或无权访问该模型。"
    elif isinstance(exc, openai.RateLimitError) or status_code == 429:
        category = "rate_limit"
        message = "模型服务当前限流，请稍后重试。"
    elif isinstance(exc, openai.APITimeoutError):
        category = "timeout"
        message = "模型服务响应超时。"
    elif isinstance(exc, openai.APIConnectionError):
        category = "network"
        message = "无法连接模型服务。"
    elif (
        isinstance(exc, (openai.BadRequestError, openai.NotFoundError))
        or status_code in {400, 404, 422}
    ):
        category = "unsupported"
        message = "当前端点或模型不支持该请求。"
    else:
        category = "unknown"
        message = "模型服务调用失败。"
    return ProviderError(category=category, message=message)
