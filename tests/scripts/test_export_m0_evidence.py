import json
from pathlib import Path

from scripts.export_m0_evidence import sanitize_probe


def test_snapshot_removes_absolute_paths_and_raw_content(tmp_path: Path):
    evidence = tmp_path / "baseline.pptx"
    evidence.write_bytes(b"pptx")
    sanitized = sanitize_probe(
        {
            "evidence": [str(evidence)],
            "details": {
                "raw": "secret",
                "api_key": "forbidden",
                "path": str(tmp_path / "nested"),
            },
        },
        tmp_path,
    )
    encoded = json.dumps(sanitized)
    assert str(tmp_path) not in encoded
    assert "secret" not in encoded
    assert "api_key" not in encoded
    assert sanitized["evidence"][0]["sha256"]
    assert sanitized["evidence"][0]["size"] == 4
