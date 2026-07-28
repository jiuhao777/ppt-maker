import json
from collections.abc import Callable
from typing import TypeVar

import openai
from pydantic import BaseModel, ValidationError

from pptmaker.providers.models import ProviderConfig
from pptmaker.providers.deepseek_http import deepseek_chat
from pptmaker.security.secrets import safe_provider_error


T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(RuntimeError):
    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


class StructuredModel:
    def __init__(
        self,
        config: ProviderConfig,
        client_factory: Callable = openai.OpenAI,
    ):
        self.config = config
        self.client_factory = client_factory

    def generate(
        self,
        schema: type[T],
        system: str,
        user: str,
        api_key: str,
    ) -> T:
        client = self.client_factory(
            api_key=api_key,
            base_url=self.config.base_url,
        )
        messages = [
            {
                "role": "system",
                "content": (
                    f"{system}\n仅返回符合以下 JSON Schema 的 JSON 对象："
                    f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
                ),
            },
            {"role": "user", "content": user},
        ]

        for attempt in range(3):
            try:
                if self.config.provider_id == "deepseek":
                    payload = deepseek_chat(
                        api_key,
                        self.config.base_url,
                        self.config.model,
                        messages,
                        response_format={"type": "json_object"},
                    )
                    content = payload["choices"][0]["message"].get(
                        "content"
                    )
                else:
                    arguments = dict(
                        model=self.config.model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0,
                        max_tokens=8192,
                    )
                    response = client.chat.completions.create(**arguments)
                    content = getattr(
                        response.choices[0].message, "content", None
                    )
            except Exception as exc:
                safe = safe_provider_error(exc)
                raise StructuredOutputError(safe.category, safe.message) from None

            try:
                return schema.model_validate_json(content)
            except (AttributeError, IndexError, ValidationError, TypeError) as exc:
                if attempt == 2:
                    msg = "模型未返回有效的结构化结果。"
                    if isinstance(exc, ValidationError):
                        fields = [e["loc"][0] if e.get("loc") else "?" for e in exc.errors(include_url=False)]
                        msg += f" 校验失败字段: {', '.join(fields[:8])}"
                    elif content is None:
                        msg += "（API 返回内容为空）"
                    else:
                        msg += "（返回内容无法解析）"
                    raise StructuredOutputError("invalid_structure", msg) from None
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "修复上一结果，仅返回合法 JSON。校验问题："
                            f"{_validation_summary(exc)}"
                        ),
                    }
                )

        raise AssertionError("unreachable")


def _validation_summary(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        details = exc.errors(include_url=False)
    else:
        details = [{"type": "missing_response_content"}]
    return json.dumps(details, ensure_ascii=False)
