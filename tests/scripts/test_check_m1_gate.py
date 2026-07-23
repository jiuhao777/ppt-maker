import json

from scripts.check_m1_gate import check_m1_gate


def _valid_artifacts(path):
    (path / "pytest.xml").write_text(
        '<testsuites tests="1" failures="0" errors="0"/>', encoding="utf-8"
    )
    for name in ("restart-recovery.json", "provider-capabilities.json"):
        (path / name).write_text(
            json.dumps({"status": "pass"}), encoding="utf-8"
        )


def test_gate_accepts_complete_safe_evidence(tmp_path):
    _valid_artifacts(tmp_path)

    assert check_m1_gate(tmp_path) == []


def test_gate_rejects_secret_in_export(tmp_path):
    _valid_artifacts(tmp_path)
    (tmp_path / "project.json").write_text(
        '{"api_key":"TEST_KEY"}', encoding="utf-8"
    )

    assert check_m1_gate(tmp_path) == ["secret leakage: project.json"]


def test_gate_rejects_missing_or_failed_evidence(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "pytest.xml").write_text(
        '<testsuites tests="1" failures="1" errors="0"/>', encoding="utf-8"
    )

    errors = check_m1_gate(tmp_path)

    assert "pytest failures or errors" in errors
    assert "missing evidence: restart-recovery.json" in errors
    assert "missing evidence: provider-capabilities.json" in errors
