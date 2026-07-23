import argparse
from pathlib import Path

from pptmaker.m0.artifacts import execute_probe
from pptmaker.m0.evidence import POLICIES
from pptmaker.m0.geometry_probe import run_geometry_probe
from pptmaker.m0.parser_probe import run_parser_core_probe
from pptmaker.m0.powerpoint_probe import run_powerpoint_probe
from pptmaker.m0.pptx_probe import build_baseline_deck
from pptmaker.m0.security_probe import run_security_probe


def _run(name: str, runner, root: Path) -> Path:
    return execute_probe(
        name,
        runner,
        root,
        source_paths=POLICIES[name].source_paths,
        source_root=root,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-office", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    baseline = root / "artifacts" / "m0" / "baseline.pptx"
    commands = [
        ("pptx-baseline", lambda: build_baseline_deck(baseline)),
        ("geometry-checks", run_geometry_probe),
        ("upload-security", lambda: run_security_probe(root)),
        ("parser-core", lambda: run_parser_core_probe(root)),
    ]
    if args.include_office:
        commands.append(
            ("powerpoint-worker", lambda: run_powerpoint_probe(root))
        )
    for name, runner in commands:
        print(_run(name, runner, root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
