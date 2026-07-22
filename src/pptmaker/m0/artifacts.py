import os
from collections.abc import Callable
from pathlib import Path

from pptmaker.m0.contracts import ProbeResult, ProbeStatus


def write_probe_result(result: ProbeResult, root: Path) -> Path:
    target = root / "artifacts" / "m0" / f"{result.name}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, target)
    return target


def execute_probe(
    name: str,
    runner: Callable[[], ProbeResult],
    root: Path,
) -> Path:
    try:
        result = runner()
        if result.name != name:
            raise ValueError(f"probe returned unexpected name: {result.name}")
    except Exception as exc:
        result = ProbeResult(
            name=name,
            status=ProbeStatus.FAIL,
            limitations=[f"{type(exc).__name__}: {exc}"],
        )
    return write_probe_result(result, root)
