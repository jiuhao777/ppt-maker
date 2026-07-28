import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from pptmaker.m3.quality import SpecQualityReport


ArtifactStatus = Literal[
    "RUNNING",
    "PPTX_READY",
    "RENDERED",
    "FAILED_RECOVERABLE",
    "COMPLETED",
]


class GenerationArtifact(BaseModel):
    schema_version: Literal[1] = 1
    project_id: str = Field(min_length=1)
    blueprint_version: int = Field(ge=1)
    status: ArtifactStatus
    pptx_path: str | None = Field(default=None, max_length=1_000)
    pptx_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    render_paths: list[str] = Field(default_factory=list, max_length=100)
    quality_report: SpecQualityReport | None = None
    safe_error_type: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @model_validator(mode="after")
    def _ready_has_pptx(self):
        if self.status in {"PPTX_READY", "RENDERED", "COMPLETED"} and (
            not self.pptx_path or not self.pptx_hash
        ):
            raise ValueError("ready artifact requires PPTX path and hash")
        return self


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified_pptx_path(
    artifact: GenerationArtifact,
    data_root: Path,
) -> Path:
    if not artifact.pptx_path or not artifact.pptx_hash:
        raise ValueError("artifact has no PPTX")
    root = Path(data_root).resolve()
    path = Path(artifact.pptx_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("artifact path escapes data directory") from exc
    if not path.is_file():
        raise ValueError("artifact PPTX is missing")
    if file_sha256(path) != artifact.pptx_hash:
        raise ValueError("artifact PPTX hash does not match")
    return path
