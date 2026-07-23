import json
from pathlib import Path

from pptmaker.m0.artifacts import execute_probe, write_probe_result
from pptmaker.m0.contracts import ProbeResult, ProbeStatus


def test_probe_result_is_written_under_artifacts(tmp_path: Path):
    (tmp_path / "tracked.py").write_text("print('probe')\n", "utf-8")
    result = ProbeResult(
        name="pptx-baseline",
        status=ProbeStatus.PASS,
        metrics={"slides": 2},
    )
    path = write_probe_result(result, tmp_path, source_paths=("tracked.py",))
    assert path == tmp_path / "artifacts" / "m0" / "pptx-baseline.json"
    assert json.loads(path.read_text("utf-8"))["metrics"]["slides"] == 2
    payload = json.loads(path.read_text("utf-8"))
    assert payload["schema_version"] == 2
    assert payload["generated_at"].endswith("Z")
    assert len(payload["source_fingerprint"]) == 64
    assert payload["environment"]["python"].startswith("3.10")


def test_execute_probe_records_runner_failure(tmp_path: Path):
    def fail():
        raise RuntimeError("probe crashed")

    path = execute_probe("upload-security", fail, tmp_path)
    payload = json.loads(path.read_text("utf-8"))
    assert payload["status"] == "fail"
    assert payload["limitations"] == ["RuntimeError: probe crashed"]


def test_execute_probe_rejects_an_unexpected_result_name(tmp_path: Path):
    def wrong_name():
        return ProbeResult(name="other", status=ProbeStatus.PASS)

    path = execute_probe("deepseek-structured-output", wrong_name, tmp_path)
    payload = json.loads(path.read_text("utf-8"))
    assert payload["name"] == "deepseek-structured-output"
    assert payload["status"] == "fail"
    assert "unexpected name" in payload["limitations"][0]
