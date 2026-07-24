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
        "max_interview_turns": 8,
        "task_type_variation": 1.0,
        "research_traceability": 1.0,
        "research_deduplication": 1.0,
        "rework_scope_accuracy": 1.0,
        "version_accuracy": 1.0,
        "version_auto_selection": 1.0,
        "freshness_route_accuracy": 0.95,
        "policy_override_accuracy": 1.0,
        "fact_traceability": 1.0,
        "unsafe_content_rejection": 1.0,
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


def test_gate_rejects_rework_outside_confirmed_scope(tmp_path):
    write_evidence(tmp_path, rework_scope_accuracy=0)

    assert check_m2_gate(tmp_path) == ["rework scope accuracy below 100%"]


def test_gate_rejects_fixed_interview_or_research_duplicates(tmp_path):
    write_evidence(
        tmp_path,
        max_interview_turns=9,
        task_type_variation=0,
        research_deduplication=0,
    )

    assert check_m2_gate(tmp_path) == [
        "max interview turns above 8",
        "task type variation below 100%",
        "research deduplication below 100%",
    ]


def test_gate_rejects_missing_version_auto_selection(tmp_path):
    write_evidence(tmp_path, version_auto_selection=0)

    assert check_m2_gate(tmp_path) == ["version auto selection below 100%"]


def test_gate_rejects_freshness_regression(tmp_path):
    write_evidence(tmp_path, freshness_route_accuracy=0.94)

    assert check_m2_gate(tmp_path) == [
        "freshness route accuracy below 95%"
    ]


def test_gate_rejects_untraceable_or_unsafe_facts(tmp_path):
    write_evidence(
        tmp_path,
        fact_traceability=0.99,
        unsafe_content_rejection=0.99,
    )

    assert check_m2_gate(tmp_path) == [
        "fact traceability below 100%",
        "unsafe content rejection below 100%",
    ]


def test_gate_rejects_policy_override_regression(tmp_path):
    write_evidence(tmp_path, policy_override_accuracy=0)

    assert check_m2_gate(tmp_path) == [
        "policy override accuracy below 100%"
    ]


def test_gate_requires_both_evidence_files(tmp_path):
    assert check_m2_gate(tmp_path) == [
        "missing evidence: pytest.xml",
        "missing evidence: evaluation.json",
    ]
