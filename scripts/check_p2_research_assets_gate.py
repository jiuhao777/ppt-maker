import sys
from pathlib import Path
from xml.etree import ElementTree


REQUIRED_TESTS = {
    "test_planning_persists_decision_without_search",
    "test_research_uses_approved_outline_gap_queries",
    "test_openverse_maps_traceable_reusable_asset",
    "test_wikimedia_maps_imageinfo_metadata",
    "test_provider_retries_rate_limit_once_then_returns_safe_error",
    "test_download_revalidates_private_redirect",
    "test_download_rejects_mime_and_decoded_format_mismatch",
    "test_curator_filters_strict_licenses_and_caps_verified_candidates",
    "test_approve_requires_asset_bound_to_blueprint_page",
    "test_verified_asset_can_be_selected_and_survives_rerun",
    "test_export_import_preserves_asset_license_mode",
}


def check_p2_research_assets_gate(artifact_dir: Path) -> list[str]:
    junit = artifact_dir / "pytest.xml"
    if not junit.exists():
        return ["missing evidence: pytest.xml"]
    root = ElementTree.parse(junit).getroot()
    failures = sum(int(node.get("failures", 0)) for node in root.iter())
    errors = sum(int(node.get("errors", 0)) for node in root.iter())
    if failures or errors:
        return ["P2 pytest failures or errors"]
    names = {
        node.get("name")
        for node in root.iter("testcase")
        if node.get("name")
    }
    missing = sorted(REQUIRED_TESTS - names)
    if missing:
        return ["missing required P2 tests: " + ", ".join(missing)]
    return []


def main() -> int:
    errors = check_p2_research_assets_gate(
        Path("artifacts/p2-research-assets")
    )
    if errors:
        print("\n".join(errors))
        return 1
    print("P2 research and assets automated gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

