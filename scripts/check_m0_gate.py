import json
from pathlib import Path


REQUIRED = (
    "pptx-baseline",
    "powerpoint-worker",
    "geometry-checks",
    "upload-security",
    "deepseek-structured-output",
    "parser-core",
)


def check_gate(root: Path, required: tuple[str, ...] = REQUIRED) -> list[str]:
    failures: list[str] = []
    for name in required:
        path = root / "artifacts" / "m0" / f"{name}.json"
        if not path.exists():
            failures.append(f"{name}: missing")
            continue
        try:
            payload = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"{name}: invalid ({type(exc).__name__})")
            continue
        status = payload.get("status")
        if payload.get("name") not in (None, name):
            failures.append(f"{name}: evidence name mismatch")
        elif status != "pass":
            failures.append(f"{name}: {status or 'missing status'}")
    return failures


def main() -> int:
    errors = check_gate(Path.cwd())
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"M0 gate passed: {len(REQUIRED)} mandatory probes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
