import json
from pathlib import Path
from xml.etree import ElementTree


def check_m3_gate(artifact_dir: Path) -> list[str]:
    errors = []
    junit = artifact_dir / "pytest.xml"
    if not junit.exists():
        errors.append("missing evidence: pytest.xml")
    else:
        root = ElementTree.parse(junit).getroot()
        failures = sum(int(n.get("failures", 0)) for n in root.iter())
        test_errors = sum(int(n.get("errors", 0)) for n in root.iter())
        if failures or test_errors:
            errors.append("pytest failures or errors")

    evaluation = artifact_dir / "evaluation.json"
    if not evaluation.exists():
        return [*errors, "missing evidence: evaluation.json"]
    try:
        metrics = json.loads(evaluation.read_text("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return [*errors, "invalid evidence: evaluation.json"]

    checks = (
        ("slide count mismatch", not metrics.get("slide_count_match", False)),
        ("element out of bounds > 0%", metrics.get("out_of_bounds_rate", 0.01) > 0),
        ("severe overlap rate > 0%", metrics.get("severe_overlap_rate", 0.01) > 0),
        ("text not editable", not metrics.get("text_editable", True)),
        ("secret leaks", metrics.get("secret_leaks", 1) != 0),
    )
    errors.extend(msg for msg, failed in checks if failed)
    return errors


def main() -> int:
    errors = check_m3_gate(Path("artifacts/m3"))
    if errors:
        print("\n".join(errors))
        return 1
    print("M3 automated gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
