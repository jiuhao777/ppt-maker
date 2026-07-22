import json
from pathlib import Path

from pptmaker.m0.vision_report import summarize
from pptmaker.m0.vision_runner import parse_review, run_manifest


class FakeAdapter:
    model_id = "fake"

    def review(self, image: Path, prompt: str) -> str:
        issue = []
        if "overflow" in image.stem:
            issue = [{
                "type": "overflow",
                "severity": "high",
                "region": "right edge",
                "evidence": "text crosses canvas",
                "suggestion": "reduce width",
                "confidence": 0.95,
            }]
        return json.dumps(
            {"slide_id": image.stem, "issues": issue, "overall_score": 90}
        )


def test_parser_accepts_single_json_code_fence():
    raw = '```json\n{"slide_id":"s1","issues":[],"overall_score":90}\n```'
    assert parse_review(raw).slide_id == "s1"


def test_runner_records_json_validity_predictions_and_metrics(tmp_path: Path):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "\n".join(
            [
                json.dumps({"case_id": "normal", "split": "development", "image": "normal.png", "expected": []}),
                json.dumps({"case_id": "overflow", "split": "development", "image": "overflow.png", "expected": ["overflow"]}),
            ]
        ),
        encoding="utf-8",
    )
    records = run_manifest(FakeAdapter(), manifest, repository_root=tmp_path)
    assert all(record["json_valid"] for record in records)
    assert records[1]["predicted"] == ["overflow"]
    assert all(record["latency_seconds"] >= 0 for record in records)


def test_report_is_computed_from_fixed_records():
    summary = summarize(
        [
            {"expected": ["overflow"], "predicted": ["overflow"], "json_valid": True, "latency_seconds": 1.0, "peak_vram_bytes": 1024},
            {"expected": [], "predicted": ["crowded"], "json_valid": True, "latency_seconds": 3.0, "peak_vram_bytes": 2048},
        ]
    )
    assert summary["precision"] == 0.5
    assert summary["recall"] == 1.0
    assert summary["false_positive_rate"] == 0.5
    assert summary["p50_seconds"] == 2.0
    assert summary["peak_vram_bytes"] == 2048
