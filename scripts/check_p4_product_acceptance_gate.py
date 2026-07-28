import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree


REQUIRED_TESTS = {
    "test_new_project_points_to_requirements",
    "test_saved_brief_advances_to_outline",
    "test_generation_error_message_never_uses_raw_exception_text",
    "test_generation_uses_blueprint_without_api_key_and_persists_download",
    "test_interrupted_generation_becomes_recoverable",
    "test_approved_blueprint_builds_reopenable_quality_deck",
    "test_acceptance_report_exposes_approved_thresholds",
}
SECRET_PATTERN = re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")


def check_p4_product_acceptance_gate(artifact_dir: Path) -> list[str]:
    junit = artifact_dir / "pytest.xml"
    metrics_path = artifact_dir / "metrics.json"
    if not junit.exists():
        return ["missing evidence: pytest.xml"]
    if not metrics_path.exists():
        return ["missing evidence: metrics.json"]
    root = ElementTree.parse(junit).getroot()
    failures = sum(int(node.get("failures", 0)) for node in root.iter())
    errors = sum(int(node.get("errors", 0)) for node in root.iter())
    if failures or errors:
        return ["P4 pytest failures or errors"]
    names = {
        node.get("name")
        for node in root.iter("testcase")
        if node.get("name")
    }
    missing = sorted(REQUIRED_TESTS - names)
    if missing:
        return ["missing required P4 tests: " + ", ".join(missing)]
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    threshold_errors = _threshold_errors(metrics)
    if threshold_errors:
        return threshold_errors
    for path in artifact_dir.rglob("*"):
        if path.is_file() and SECRET_PATTERN.search(
            path.read_text(encoding="utf-8", errors="ignore")
        ):
            return [f"secret-like value found in evidence: {path.name}"]
    return []


def _threshold_errors(metrics: dict) -> list[str]:
    checks = {
        "requirement_coverage": metrics.get("requirement_coverage", 0) >= 0.90,
        "title_conclusion_rate": metrics.get("title_conclusion_rate", 0) >= 0.90,
        "severe_geometry_defects": metrics.get("severe_geometry_defects", 1) == 0,
        "density_violation_rate": metrics.get("density_violation_rate", 1) <= 0.05,
        "public_fact_traceability": metrics.get("public_fact_traceability", 0) >= 0.95,
        "asset_attribution_rate": metrics.get("asset_attribution_rate", 0) == 1.0,
        "file_reopens": metrics.get("file_reopens") is True,
        "passed": metrics.get("passed") is True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return ["acceptance thresholds failed: " + ", ".join(failed)] if failed else []


def main() -> int:
    errors = check_p4_product_acceptance_gate(
        Path("artifacts/p4-product-acceptance")
    )
    if errors:
        print("\n".join(errors))
        return 1
    print("P4 product acceptance automated gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
