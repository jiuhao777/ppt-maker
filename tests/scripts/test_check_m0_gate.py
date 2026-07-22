import json
from pathlib import Path

from scripts.check_m0_gate import check_gate


def _write(root: Path, name: str, payload: dict) -> None:
    folder = root / "artifacts" / "m0"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(payload), "utf-8")


def test_gate_fails_when_mandatory_probe_failed(tmp_path: Path):
    _write(tmp_path, "pptx-baseline", {"name": "pptx-baseline", "status": "fail"})
    assert check_gate(tmp_path, required=("pptx-baseline",)) == ["pptx-baseline: fail"]


def test_gate_reports_missing_invalid_and_name_mismatch(tmp_path: Path):
    folder = tmp_path / "artifacts" / "m0"
    folder.mkdir(parents=True)
    (folder / "invalid.json").write_text("not-json", "utf-8")
    _write(tmp_path, "wrong", {"name": "another-probe", "status": "pass"})

    assert check_gate(tmp_path, required=("missing", "invalid", "wrong")) == [
        "missing: missing",
        "invalid: invalid (JSONDecodeError)",
        "wrong: evidence name mismatch",
    ]


def test_gate_passes_only_complete_pass_evidence(tmp_path: Path):
    _write(tmp_path, "probe", {"name": "probe", "status": "pass"})
    assert check_gate(tmp_path, required=("probe",)) == []
