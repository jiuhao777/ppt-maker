import json
from scripts.check_m3_gate import (
    REQUIRED_LAYOUTS,
    REQUIRED_PAGE_TYPES,
    check_m3_gate,
)


def _write(root, **changes):
    (root / "pytest.xml").write_text('<testsuite tests="1" failures="0" errors="0"/>', encoding="utf-8")
    metrics = {
        "layouts_exercised": sorted(REQUIRED_LAYOUTS),
        "page_types_exercised": sorted(REQUIRED_PAGE_TYPES),
        "crashes": [],
        "slide_count_match": True,
        "out_of_bounds_rate": 0,
        "severe_overlap_rate": 0,
        "text_editable": True,
        "secret_leaks": 0,
    }
    metrics.update(changes)
    (root / "evaluation.json").write_text(json.dumps(metrics), encoding="utf-8")


def test_gate_accepts_perfect_evidence(tmp_path):
    _write(tmp_path)
    assert check_m3_gate(tmp_path) == []


def test_gate_rejects_slide_count_mismatch(tmp_path):
    _write(tmp_path, slide_count_match=False)
    assert "slide count mismatch" in check_m3_gate(tmp_path)[0]

def test_gate_rejects_out_of_bounds(tmp_path):
    _write(tmp_path, out_of_bounds_rate=0.01)
    assert "out of bounds" in check_m3_gate(tmp_path)[0]

def test_gate_rejects_secret_leaks(tmp_path):
    _write(tmp_path, secret_leaks=1)
    assert "secret leaks" in check_m3_gate(tmp_path)[0]


def test_gate_rejects_missing_layout_coverage(tmp_path):
    _write(tmp_path, layouts_exercised=["text"])
    assert "missing layout coverage" in check_m3_gate(tmp_path)[0]


def test_gate_requires_both_evidence_files(tmp_path):
    assert len(check_m3_gate(tmp_path)) == 2
