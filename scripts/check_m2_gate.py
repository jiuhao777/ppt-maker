import json
import sys
from pathlib import Path
from xml.etree import ElementTree


def check_m2_gate(artifact_dir: Path) -> list[str]:
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

    evaluation_path = artifact_dir / "evaluation.json"
    if not evaluation_path.exists():
        errors.append("missing evidence: evaluation.json")
        return errors
    try:
        metrics = json.loads(evaluation_path.read_text("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return [*errors, "invalid evidence: evaluation.json"]

    checks = (
        ("key field coverage below 90%", metrics.get("key_field_coverage", 0) < 0.90),
        (
            "invalid question rate above 10%",
            metrics.get("invalid_question_rate", 1) > 0.10,
        ),
        (
            "mean interview turns above 15",
            metrics.get("mean_interview_turns", 16) > 15,
        ),
        (
            "max interview turns above 8",
            metrics.get("max_interview_turns", 9) > 8,
        ),
        (
            "task type variation below 100%",
            metrics.get("task_type_variation", 0) < 1,
        ),
        (
            "research traceability below 100%",
            metrics.get("research_traceability", 0) < 1,
        ),
        (
            "research deduplication below 100%",
            metrics.get("research_deduplication", 0) < 1,
        ),
        (
            "rework scope accuracy below 100%",
            metrics.get("rework_scope_accuracy", 0) < 1,
        ),
        ("version accuracy below 100%", metrics.get("version_accuracy", 0) < 1),
        (
            "version auto selection below 100%",
            metrics.get("version_auto_selection", 0) < 1,
        ),
        (
            f"approval violations: {metrics.get('approval_violations', 1)}",
            metrics.get("approval_violations", 1) != 0,
        ),
        ("secret leakage", metrics.get("secret_leaks", 1) != 0),
    )
    errors.extend(message for message, failed in checks if failed)
    return errors


def main() -> int:
    errors = check_m2_gate(Path("artifacts/m2"))
    if errors:
        print("\n".join(errors))
        return 1
    print("M2 automated gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
