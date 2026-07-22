from pathlib import Path

from pptmaker.m0.security_probe import run_security_probe


def test_security_probe_records_all_baseline_challenges(tmp_path: Path):
    result = run_security_probe(tmp_path)

    assert result.status.value == "pass"
    assert result.metrics["challenge_checks"] == 6
    assert result.metrics["passed_checks"] == 6
    assert all(result.details["checks"].values())
