from datetime import datetime, timezone

import pytest

from pptmaker.m3.artifacts import (
    GenerationArtifact,
    file_sha256,
    verified_pptx_path,
)


def artifact(path, **updates):
    values = {
        "project_id": "p1",
        "blueprint_version": 1,
        "status": "COMPLETED",
        "pptx_path": str(path),
        "pptx_hash": file_sha256(path),
        "created_at": datetime(2026, 7, 27, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 7, 27, tzinfo=timezone.utc),
    }
    values.update(updates)
    return GenerationArtifact(**values)


def test_verified_path_requires_containment_and_matching_hash(tmp_path):
    path = tmp_path / "deck.pptx"
    path.write_bytes(b"deck")

    assert verified_pptx_path(artifact(path), tmp_path) == path.resolve()

    with pytest.raises(ValueError, match="hash"):
        verified_pptx_path(
            artifact(path, pptx_hash="0" * 64), tmp_path
        )


def test_verified_path_rejects_escape(tmp_path):
    outside = tmp_path.parent / "outside.pptx"
    outside.write_bytes(b"deck")
    try:
        with pytest.raises(ValueError, match="escapes"):
            verified_pptx_path(artifact(outside), tmp_path)
    finally:
        outside.unlink(missing_ok=True)


def test_ready_status_requires_file_metadata():
    with pytest.raises(ValueError, match="requires"):
        GenerationArtifact(
            project_id="p1",
            blueprint_version=1,
            status="PPTX_READY",
        )
