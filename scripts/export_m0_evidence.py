import argparse
import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree

from pptmaker.m0.evidence import POLICIES


SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "raw",
    "prompt",
    "response_body",
}
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_path(value: str, root: Path):
    if not (WINDOWS_ABSOLUTE.match(value) or value.startswith("/")):
        return value
    path = Path(value)
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return "<redacted-absolute-path>"
    return relative


def _sanitize(value, root: Path):
    if isinstance(value, dict):
        return {
            key: _sanitize(item, root)
            for key, item in sorted(value.items())
            if key.lower() not in SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize(item, root) for item in value]
    if isinstance(value, str):
        return _safe_path(value, root)
    return value


def sanitize_probe(payload: dict, root: Path) -> dict:
    sanitized = _sanitize(payload, root)
    evidence = []
    for original in payload.get("evidence", []):
        path = Path(original)
        if not path.is_absolute():
            path = root / path
        try:
            relative = path.resolve().relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            evidence.append({"path": "<redacted-absolute-path>"})
            continue
        item = {"path": relative}
        if path.is_file():
            item.update({"sha256": _sha256(path), "size": path.stat().st_size})
        evidence.append(item)
    sanitized["evidence"] = evidence
    return sanitized


def _test_summary(junitxml: Path) -> dict[str, int]:
    root = ElementTree.parse(junitxml).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    return {
        name: sum(int(suite.attrib.get(name, 0)) for suite in suites)
        for name in ("tests", "failures", "errors", "skipped")
    }


def export_evidence(repository_root: Path, junitxml: Path) -> Path:
    destination = repository_root / "docs" / "evidence" / "m0"
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    for name in POLICIES:
        source = repository_root / "artifacts" / "m0" / f"{name}.json"
        payload = json.loads(source.read_text("utf-8"))
        target = destination / f"{name}.json"
        target.write_text(
            json.dumps(
                sanitize_probe(payload, repository_root),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        files.append(
            {
                "path": target.relative_to(repository_root).as_posix(),
                "sha256": _sha256(target),
                "size": target.stat().st_size,
            }
        )
    manifest = {
        "schema_version": 1,
        "tests": _test_summary(junitxml),
        "files": sorted(files, key=lambda item: item["path"]),
    }
    target = destination / "manifest.json"
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junitxml", type=Path, required=True)
    args = parser.parse_args()
    print(export_evidence(Path.cwd(), args.junitxml))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
