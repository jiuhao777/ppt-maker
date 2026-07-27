import sys
from pathlib import Path
from xml.etree import ElementTree


REQUIRED_TESTS = {
    "test_page_rejects_more_than_three_supporting_points",
    "test_review_accepts_valid_blueprint",
    "test_approve_supersedes_old_approved_version",
    "test_generator_uses_skeleton_then_page_batches",
    "test_generator_never_sends_excluded_facts",
    "test_generator_requires_approved_outline",
    "test_m3_generation_is_hidden_until_blueprint_approved",
    "test_m3_generation_appears_after_blueprint_approval",
    "test_pending_blueprint_version_is_applied_before_widget",
}


def check_p1_blueprint_gate(artifact_dir: Path) -> list[str]:
    junit = artifact_dir / "pytest.xml"
    if not junit.exists():
        return ["missing evidence: pytest.xml"]

    root = ElementTree.parse(junit).getroot()
    failures = sum(int(node.get("failures", 0)) for node in root.iter())
    errors = sum(int(node.get("errors", 0)) for node in root.iter())
    if failures or errors:
        return ["blueprint pytest failures or errors"]

    names = {
        node.get("name")
        for node in root.iter("testcase")
        if node.get("name")
    }
    missing = sorted(REQUIRED_TESTS - names)
    if missing:
        return [
            "missing required blueprint tests: " + ", ".join(missing)
        ]
    return []


def main() -> int:
    errors = check_p1_blueprint_gate(Path("artifacts/p1-blueprint"))
    if errors:
        print("\n".join(errors))
        return 1
    print("P1 Blueprint automated gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
