import json
import sys
from pathlib import Path
from xml.etree import ElementTree


EVIDENCE = ("restart-recovery.json", "provider-capabilities.json")


def check_m1_gate(artifact_dir: Path) -> list[str]:
    errors = []
    junit = artifact_dir / "pytest.xml"
    if not junit.exists():
        errors.append("missing evidence: pytest.xml")
    else:
        root = ElementTree.parse(junit).getroot()
        failures = sum(int(node.get("failures", 0)) for node in root.iter())
        test_errors = sum(int(node.get("errors", 0)) for node in root.iter())
        if failures or test_errors:
            errors.append("pytest failures or errors")

    for name in EVIDENCE:
        path = artifact_dir / name
        if not path.exists():
            errors.append(f"missing evidence: {name}")
            continue
        try:
            if json.loads(path.read_text("utf-8")).get("status") != "pass":
                errors.append(f"failed evidence: {name}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            errors.append(f"invalid evidence: {name}")

    for path in artifact_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".json", ".log", ".db", ".sqlite"}:
            if b"TEST_KEY" in path.read_bytes():
                errors.append(f"secret leakage: {path.relative_to(artifact_dir)}")
    return errors


def main() -> int:
    errors = check_m1_gate(Path("artifacts/m1"))
    if errors:
        print("\n".join(errors))
        return 1
    print("M1 automated gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
