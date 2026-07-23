import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from pptmaker.m0.contracts import ProbeResult, ProbeStatus
from pptmaker.m0.evidence import runtime_environment, source_fingerprint


def write_probe_result(
    result: ProbeResult,
    root: Path,
    *,
    source_paths: tuple[str, ...] = (),
    source_root: Path | None = None,
) -> Path:
    result = result.model_copy(
        update={
            "schema_version": 2,
            "generated_at": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "source_fingerprint": source_fingerprint(
                source_root or root, source_paths
            ),
            "environment": runtime_environment(),
        }
    )
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
    *,
    source_paths: tuple[str, ...] = (),
    source_root: Path | None = None,
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
    return write_probe_result(
        result,
        root,
        source_paths=source_paths,
        source_root=source_root,
    )
