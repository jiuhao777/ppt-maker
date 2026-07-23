import json

from scripts.check_m2_gate import check_m2_gate


def write_evidence(root, **changes):
    (root / "pytest.xml").write_text(
        '<testsuite tests="1" failures="0" errors="0"/>',
        encoding="utf-8",
    )
    metrics = {
        "key_field_coverage": 0.90,
        "invalid_question_rate": 0.10,
        "mean_interview_turns": 15,
        "research_traceability": 1.0,
        "version_accuracy": 1.0,
        "approval_violations": 0,
        "secret_leaks": 0,
    }
    metrics.update(changes)
    (root / "evaluation.json").write_text(
        json.dumps(metrics),
        encoding="utf-8",
    )


def test_gate_accepts_exact_thresholds(tmp_path):
    write_evidence(tmp_path)

    assert check_m2_gate(tmp_path) == []


def test_gate_rejects_unapproved_transition(tmp_path):
    write_evidence(tmp_path, approval_violations=1)

    assert check_m2_gate(tmp_path) == ["approval violations: 1"]


def test_gate_rejects_missing_research_traceability(tmp_path):
    write_evidence(tmp_path, research_traceability=0.95)

    assert check_m2_gate(tmp_path) == ["research traceability below 100%"]


def test_gate_requires_both_evidence_files(tmp_path):
    assert check_m2_gate(tmp_path) == [
        "missing evidence: pytest.xml",
        "missing evidence: evaluation.json",
    ]
