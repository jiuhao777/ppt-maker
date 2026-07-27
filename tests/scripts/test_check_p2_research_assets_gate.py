from scripts.check_p2_research_assets_gate import (
    REQUIRED_TESTS,
    check_p2_research_assets_gate,
)


def _write_junit(root, names=None, *, failures=0):
    selected = names if names is not None else REQUIRED_TESTS
    cases = "".join(f'<testcase name="{name}"/>' for name in selected)
    (root / "pytest.xml").write_text(
        f'<testsuite tests="{len(selected)}" failures="{failures}" '
        f'errors="0">{cases}</testsuite>',
        encoding="utf-8",
    )


def test_gate_accepts_required_passing_tests(tmp_path):
    _write_junit(tmp_path)
    assert check_p2_research_assets_gate(tmp_path) == []


def test_gate_rejects_missing_security_test(tmp_path):
    _write_junit(
        tmp_path,
        REQUIRED_TESTS - {"test_download_revalidates_private_redirect"},
    )
    assert check_p2_research_assets_gate(tmp_path) == [
        "missing required P2 tests: "
        "test_download_revalidates_private_redirect"
    ]


def test_gate_rejects_test_failure(tmp_path):
    _write_junit(tmp_path, failures=1)
    assert check_p2_research_assets_gate(tmp_path) == [
        "P2 pytest failures or errors"
    ]


def test_gate_requires_junit(tmp_path):
    assert check_p2_research_assets_gate(tmp_path) == [
        "missing evidence: pytest.xml"
    ]

