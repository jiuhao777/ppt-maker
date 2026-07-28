from scripts.check_p3_blueprint_pptx_gate import (
    PAGE_TYPES,
    REQUIRED_TESTS,
    check_p3_blueprint_pptx_gate,
)


def _names():
    return REQUIRED_TESTS | {
        f"test_every_formal_page_type_stays_in_canvas[{page_type}]"
        for page_type in PAGE_TYPES
    }


def _write(root, names=None, failures=0):
    selected = _names() if names is None else names
    cases = "".join(f'<testcase name="{name}"/>' for name in selected)
    (root / "pytest.xml").write_text(
        f'<testsuite tests="{len(selected)}" failures="{failures}" '
        f'errors="0">{cases}</testsuite>',
        encoding="utf-8",
    )


def test_p3_gate_accepts_complete_evidence(tmp_path):
    _write(tmp_path)
    assert check_p3_blueprint_pptx_gate(tmp_path) == []


def test_p3_gate_rejects_missing_native_chart_test(tmp_path):
    _write(tmp_path, _names() - {"test_native_chart_remains_editable"})
    assert check_p3_blueprint_pptx_gate(tmp_path) == [
        "missing required P3 tests: test_native_chart_remains_editable"
    ]


def test_p3_gate_rejects_missing_page_type(tmp_path):
    _write(
        tmp_path,
        _names()
        - {"test_every_formal_page_type_stays_in_canvas[timeline]"},
    )
    assert check_p3_blueprint_pptx_gate(tmp_path) == [
        "missing formal page types: timeline"
    ]


def test_p3_gate_rejects_failures_and_missing_junit(tmp_path):
    assert check_p3_blueprint_pptx_gate(tmp_path) == [
        "missing evidence: pytest.xml"
    ]
    _write(tmp_path, failures=1)
    assert check_p3_blueprint_pptx_gate(tmp_path) == [
        "P3 pytest failures or errors"
    ]
