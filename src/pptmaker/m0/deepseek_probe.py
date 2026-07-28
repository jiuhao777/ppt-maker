import os
import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from pptmaker.m0.contracts import ProbeResult, ProbeStatus
from pptmaker.providers.deepseek_http import deepseek_chat


class OutlineProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=100)
    slides: list[str] = Field(min_length=3, max_length=12)


def parse_outline(raw: str) -> OutlineProbe:
    return OutlineProbe.model_validate_json(raw)


Requester = Callable[[list[dict[str, str]]], tuple[str, int, int]]


BASE_MESSAGES = [
    {
        "role": "system",
        "content": (
            "只输出 JSON 对象，字段严格为 title:string 和 slides:string[3..12]，"
            "不得使用 Markdown 代码块或增加其他字段。"
            '示例：{"title":"项目汇报","slides":["背景","方案","结果"]}'
        ),
    },
    {
        "role": "user",
        "content": "为面向中国求职作品展示的 AI PPT 生成器创建项目汇报大纲。",
    },
]


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * fraction + 0.999999) - 1))
    return ordered[index]


def _error_category(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return "timeout"
    if "ratelimit" in name or "rate_limit" in name:
        return "rate_limit"
    return "other"


def _safe_error_signature(exc: Exception) -> str:
    message = str(exc)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        safe_body = {
            key: body.get(key)
            for key in ("code", "message", "param", "type")
            if body.get(key) is not None
        }
        if safe_body:
            message += " " + json.dumps(safe_body, ensure_ascii=False)
    message = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-<redacted>", message)
    message = re.sub(
        r"(?i)(authorization|api[_-]?key|bearer)(\s*[:=]?\s*)\S+",
        r"\1\2<redacted>",
        message,
    )
    return f"{type(exc).__name__}: {message[:500]}"


def run_structured_probe(requester: Requester, iterations: int = 20) -> ProbeResult:
    if iterations < 1:
        raise ValueError("iterations must be positive")

    first_pass = repaired_pass = empty = repair_requests = 0
    error_counts = {"timeout": 0, "rate_limit": 0, "other": 0}
    error_types: dict[str, int] = {}
    error_signatures: dict[str, int] = {}
    latencies: list[float] = []
    prompt_tokens = completion_tokens = 0

    for _ in range(iterations):
        started = time.perf_counter()
        try:
            raw, prompt, completion = requester(BASE_MESSAGES)
            prompt_tokens += prompt
            completion_tokens += completion
            if not raw:
                empty += 1
            else:
                try:
                    parse_outline(raw)
                    first_pass += 1
                    repaired_pass += 1
                except Exception:
                    repair_requests += 1
                    repair_messages = [
                        {
                            "role": "system",
                            "content": (
                                "将输入修复为严格满足 title:string、slides:string[3..12] "
                                "且无额外字段的 JSON 对象。只输出 JSON，只修复一次。"
                            ),
                        },
                        {"role": "user", "content": raw},
                    ]
                    fixed, repair_prompt, repair_completion = requester(repair_messages)
                    prompt_tokens += repair_prompt
                    completion_tokens += repair_completion
                    parse_outline(fixed)
                    repaired_pass += 1
        except Exception as exc:
            error_counts[_error_category(exc)] += 1
            error_name = type(exc).__name__
            error_types[error_name] = error_types.get(error_name, 0) + 1
            signature = _safe_error_signature(exc)
            error_signatures[signature] = error_signatures.get(signature, 0) + 1
        finally:
            latencies.append(time.perf_counter() - started)

    first_rate = first_pass / iterations
    repaired_rate = repaired_pass / iterations
    passed = first_rate >= 0.95 and repaired_rate == 1.0
    return ProbeResult(
        name="deepseek-structured-output",
        status=ProbeStatus.PASS if passed else ProbeStatus.FAIL,
        metrics={
            "iterations": iterations,
            "first_pass_rate": first_rate,
            "repaired_pass_rate": repaired_rate,
            "repair_requests": repair_requests,
            "empty_responses": empty,
            "timeouts": error_counts["timeout"],
            "rate_limits": error_counts["rate_limit"],
            "other_errors": error_counts["other"],
            "p50_seconds": _percentile(latencies, 0.50),
            "p95_seconds": _percentile(latencies, 0.95),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
        limitations=[
            "Results apply to the configured DeepSeek model and endpoint at probe time."
        ],
        details={
            "error_counts": error_counts,
            "error_types": error_types,
            "error_signatures": error_signatures,
        },
    )


def _online_requester(
    key: str,
    base_url: str,
    model: str,
) -> Requester:
    def request(messages: list[dict[str, str]]) -> tuple[str, int, int]:
        response = deepseek_chat(
            key,
            base_url,
            model,
            messages,
            response_format={"type": "json_object"},
            max_tokens=512,
        )
        usage: Any = response.get("usage") or {}
        return (
            response["choices"][0]["message"].get("content") or "",
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
        )

    return request


def run_online_probe(iterations: int = 20) -> ProbeResult:
    key = os.environ["DEEPSEEK_API_KEY"]
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    result = run_structured_probe(
        _online_requester(key, base_url, model),
        iterations=iterations,
    )
    return result.model_copy(
        update={
            "details": {
                **result.details,
                "model": model,
                "base_url_host": urlsplit(base_url).hostname or "",
            }
        }
    )


def main(root: Path | None = None) -> Path:
    from pptmaker.m0.artifacts import execute_probe
    from pptmaker.m0.evidence import POLICIES

    repository_root = root or Path.cwd()
    return execute_probe(
        "deepseek-structured-output",
        run_online_probe,
        repository_root,
        source_paths=POLICIES["deepseek-structured-output"].source_paths,
        source_root=Path.cwd(),
    )


if __name__ == "__main__":
    print(main())
