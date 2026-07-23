import hashlib
import platform
import sys
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable


MetricCheck = Callable[[object], bool]


@dataclass(frozen=True)
class ProbePolicy:
    source_paths: tuple[str, ...]
    metric_checks: dict[str, MetricCheck] = field(default_factory=dict)
    require_evidence: bool = False


def source_fingerprint(root: Path, paths: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(paths):
        normalized = Path(relative).as_posix()
        content = (root / relative).read_bytes()
        name = normalized.encode("utf-8")
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _package_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "not-installed"


def runtime_environment() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "platform": sys.platform,
        "ppt-maker": _package_version("ppt-maker"),
        "pydantic": _package_version("pydantic"),
        "python-pptx": _package_version("python-pptx"),
        "pywin32": _package_version("pywin32"),
        "psutil": _package_version("psutil"),
    }


COMMON = ("pyproject.toml", "requirements/ai-py310-win.lock.txt")

POLICIES: dict[str, ProbePolicy] = {
    "pptx-baseline": ProbePolicy(
        source_paths=COMMON + ("src/pptmaker/m0/pptx_probe.py",),
        metric_checks={"slides": lambda value: value == 2},
        require_evidence=True,
    ),
    "powerpoint-worker": ProbePolicy(
        source_paths=COMMON
        + (
            "src/pptmaker/m0/powerpoint_probe.py",
            "src/pptmaker/powerpoint/client.py",
            "src/pptmaker/powerpoint/worker.py",
            "src/pptmaker/powerpoint/protocol.py",
            "src/pptmaker/powerpoint/preflight.py",
        ),
        metric_checks={
            "rendered_slides": lambda value: value == 2,
            "timeout_orphaned": lambda value: value is False,
        },
        require_evidence=True,
    ),
    "geometry-checks": ProbePolicy(
        source_paths=COMMON
        + (
            "src/pptmaker/m0/geometry_probe.py",
            "src/pptmaker/evaluation/geometry.py",
        ),
        metric_checks={"passed": lambda value: value == 4},
    ),
    "upload-security": ProbePolicy(
        source_paths=COMMON
        + (
            "src/pptmaker/m0/security_probe.py",
            "src/pptmaker/security/fetcher.py",
            "src/pptmaker/security/network.py",
            "src/pptmaker/security/uploads.py",
        ),
        metric_checks={"passed_checks": lambda value: value >= 8},
    ),
    "deepseek-structured-output": ProbePolicy(
        source_paths=COMMON + ("src/pptmaker/m0/deepseek_probe.py",),
        metric_checks={
            "iterations": lambda value: value == 20,
            "first_pass_rate": lambda value: value >= 0.95,
            "repaired_pass_rate": lambda value: value == 1.0,
        },
    ),
    "parser-core": ProbePolicy(
        source_paths=COMMON + ("src/pptmaker/m0/parser_probe.py",),
        metric_checks={"passed_checks": lambda value: value == 3},
    ),
}
