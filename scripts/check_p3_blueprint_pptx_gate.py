import sys
from pathlib import Path
from xml.etree import ElementTree


PAGE_TYPES = {
    "cover", "contents", "section", "conclusion", "text", "image_text",
    "cards", "comparison", "timeline", "process", "architecture",
    "data_chart", "case", "quote", "interaction", "qa", "ending",
}
REQUIRED_TESTS = {
    "test_compiler_requires_approved_blueprint",
    "test_compiler_requires_bound_approved_local_image",
    "test_compiler_emits_native_chart_data",
    "test_image_placeholder_is_rejected",
    "test_verified_image_is_cropped_not_stretched",
    "test_native_chart_remains_editable",
    "test_notes_sources_footer_line_and_transition",
    "test_missing_image_leaves_no_published_file",
    "test_repair_reduces_defects_and_preserves_unaffected_page",
    "test_specs_and_artifact_round_trip",
    "test_running_artifact_recovers_after_restart",
    "test_generation_uses_blueprint_without_api_key_and_persists_download",
    "test_interrupted_generation_becomes_recoverable",
}


def check_p3_blueprint_pptx_gate(artifact_dir: Path) -> list[str]:
    junit = artifact_dir / "pytest.xml"
    if not junit.exists():
        return ["missing evidence: pytest.xml"]
    root = ElementTree.parse(junit).getroot()
    failures = sum(int(node.get("failures", 0)) for node in root.iter())
    errors = sum(int(node.get("errors", 0)) for node in root.iter())
    if failures or errors:
        return ["P3 pytest failures or errors"]
    names = {
        node.get("name")
        for node in root.iter("testcase")
        if node.get("name")
    }
    missing = sorted(REQUIRED_TESTS - names)
    if missing:
        return ["missing required P3 tests: " + ", ".join(missing)]
    missing_pages = sorted(
        page_type
        for page_type in PAGE_TYPES
        if (
            f"test_every_formal_page_type_stays_in_canvas"
            f"[{page_type}]"
        )
        not in names
    )
    if missing_pages:
        return ["missing formal page types: " + ", ".join(missing_pages)]
    return []


def main() -> int:
    errors = check_p3_blueprint_pptx_gate(
        Path("artifacts/p3-blueprint-pptx")
    )
    if errors:
        print("\n".join(errors))
        return 1
    print("P3 Blueprint-to-PPTX automated gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
