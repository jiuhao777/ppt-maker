import json

from scripts.check_p4_product_acceptance_gate import (
    REQUIRED_TESTS,
    check_p4_product_acceptance_gate,
)


METRICS = {
    "requirement_coverage": 1.0,
    "title_conclusion_rate": 1.0,
    "severe_geometry_defects": 0,
    "density_violation_rate": 0.0,
    "public_fact_traceability": 1.0,
    "asset_download_safety_rate": 1.0,
    "file_reopens": True,
    "passed": True,
}


def _write(root, names=REQUIRED_TESTS, metrics=METRICS):
    cases = "".join(f'<testcase name="{name}"/>' for name in names)
    (root / "pytest.xml").write_text(
        f'<testsuite tests="{len(names)}" failures="0" errors="0">{cases}</testsuite>',
        encoding="utf-8",
    )
    (root / "metrics.json").write_text(
        json.dumps(metrics), encoding="utf-8"
    )


def test_p4_gate_accepts_complete_evidence(tmp_path):
    _write(tmp_path)
    assert check_p4_product_acceptance_gate(tmp_path) == []


def test_p4_gate_rejects_missing_test_and_metrics(tmp_path):
    assert check_p4_product_acceptance_gate(tmp_path) == [
        "missing evidence: pytest.xml"
    ]
    _write(tmp_path, names=REQUIRED_TESTS - {"test_new_project_points_to_requirements"})
    assert "missing required P4 tests" in check_p4_product_acceptance_gate(tmp_path)[0]


def test_p4_gate_rejects_failed_threshold_or_secret(tmp_path):
    _write(tmp_path, metrics={**METRICS, "file_reopens": False})
    assert "file_reopens" in check_p4_product_acceptance_gate(tmp_path)[0]
    _write(tmp_path)
    (tmp_path / "unsafe.txt").write_text(
        "sk-" + "x" * 20, encoding="utf-8"
    )
    assert "secret-like value" in check_p4_product_acceptance_gate(tmp_path)[0]
