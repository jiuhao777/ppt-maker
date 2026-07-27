from scripts.check_p1_blueprint_gate import (
    REQUIRED_TESTS,
    check_p1_blueprint_gate,
)


def _write_junit(root, names=None, *, failures=0):
    cases = "".join(
        f'<testcase name="{name}"/>' for name in (names or REQUIRED_TESTS)
    )
    (root / "pytest.xml").write_text(
        f'<testsuite tests="{len(names or REQUIRED_TESTS)}" '
        f'failures="{failures}" errors="0">{cases}</testsuite>',
        encoding="utf-8",
    )


def test_gate_accepts_required_passing_tests(tmp_path):
    _write_junit(tmp_path)
    assert check_p1_blueprint_gate(tmp_path) == []


def test_gate_rejects_missing_contract_test(tmp_path):
    _write_junit(tmp_path, names=set(REQUIRED_TESTS) - {
        "test_generator_uses_skeleton_then_page_batches"
    })
    assert check_p1_blueprint_gate(tmp_path) == [
        "missing required blueprint tests: "
        "test_generator_uses_skeleton_then_page_batches"
    ]


def test_gate_rejects_test_failure(tmp_path):
    _write_junit(tmp_path, failures=1)
    assert check_p1_blueprint_gate(tmp_path) == [
        "blueprint pytest failures or errors"
    ]


def test_gate_requires_junit(tmp_path):
    assert check_p1_blueprint_gate(tmp_path) == [
        "missing evidence: pytest.xml"
    ]
