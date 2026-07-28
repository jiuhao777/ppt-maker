from collections.abc import Callable
import json

import openai

from pptmaker.providers.models import Capability, CapabilityReport, ProviderConfig
from pptmaker.security.secrets import safe_provider_error


class OpenAICompatibleProvider:
    def __init__(
        self,
        config: ProviderConfig,
        client_factory: Callable = openai.OpenAI,
    ):
        self.config = config
        self.client_factory = client_factory

    def probe(self, api_key: str) -> CapabilityReport:
        unknown = Capability(value="unknown", source="unknown")
        capabilities = {
            "vision": unknown,
            "max_context": unknown,
        }
        warnings = []
        try:
            client = self.client_factory(
                api_key=api_key,
                base_url=self.config.base_url,
            )
            common = {
                "model": self.config.model,
                "messages": [
                    {"role": "user", "content": "Reply with the word OK."}
                ],
                "temperature": 0,
                "max_tokens": 16,
            }
            client.chat.completions.create(**common)
            capabilities["basic_completion"] = Capability(
                value=True, source="probed"
            )

            structured = self._optional_probe(
                client,
                {
                    **common,
                    "messages": [
                        {"role": "user", "content": "Return a JSON object."}
                    ],
                    "response_format": {"type": "json_object"},
                },
                self._has_json_content,
            )
            capabilities["structured_output"] = Capability(
                value=structured, source="probed"
            )
            if not structured:
                warnings.append("该模型不支持结构化输出。")

            tools = self._optional_probe(
                client,
                {
                    **common,
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "ping",
                                "description": "Return a health check.",
                                "parameters": {
                                    "type": "object",
                                    "properties": {},
                                },
                            },
                        }
                    ],
                    "tool_choice": {
                        "type": "function",
                        "function": {"name": "ping"},
                    },
                },
                self._has_ping_tool_call,
            )
            capabilities["tools"] = Capability(value=tools, source="probed")
            if not tools:
                warnings.append("该模型不支持工具调用。")
            return CapabilityReport(
                status="success",
                capabilities=capabilities,
                warnings=warnings,
            )
        except Exception as exc:
            return CapabilityReport(
                status="failed",
                capabilities=capabilities,
                error=safe_provider_error(exc),
            )

    @staticmethod
    def _optional_probe(client, arguments: dict, validator: Callable) -> bool:
        try:
            response = client.chat.completions.create(**arguments)
            return validator(response)
        except (openai.BadRequestError, openai.NotFoundError):
            return False

    @staticmethod
    def _has_json_content(response) -> bool:
        try:
            json.loads(response.choices[0].message.content)
            return True
        except (AttributeError, IndexError, TypeError, json.JSONDecodeError):
            return False

    @staticmethod
    def _has_ping_tool_call(response) -> bool:
        try:
            calls = response.choices[0].message.tool_calls or []
            return any(call.function.name == "ping" for call in calls)
        except (AttributeError, IndexError, TypeError):
            return False


def provider_for(config: ProviderConfig) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(config)
