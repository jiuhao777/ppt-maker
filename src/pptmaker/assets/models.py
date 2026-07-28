from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


AssetStatus = Literal["CANDIDATE", "APPROVED", "REJECTED"]
LicenseMode = Literal["STRICT", "LOOSE"]
LicenseStatus = Literal["REUSABLE", "RESTRICTED", "UNKNOWN"]


class AssetCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=200)
    provider: str = Field(min_length=1, max_length=100)
    original_url: HttpUrl
    landing_url: HttpUrl
    thumbnail_url: HttpUrl
    creator: str | None = Field(default=None, max_length=300)
    license_name: str | None = Field(default=None, max_length=100)
    license_url: HttpUrl | None = None
    license_status: LicenseStatus
    attribution: str = Field(default="", max_length=1_000)
    width: int = Field(ge=1, le=12_000)
    height: int = Field(ge=1, le=12_000)


class AssetRecord(AssetCandidate):
    schema_version: Literal[1] = 1
    project_id: str = Field(min_length=1)
    blueprint_version: int = Field(ge=1)
    page_id: str = Field(min_length=1)
    slot_id: str = Field(default="hero", min_length=1, max_length=100)
    license_mode: LicenseMode
    accessed_at: datetime
    status: AssetStatus = "CANDIDATE"
    local_path: str | None = Field(default=None, max_length=1_000)
    content_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    mime_type: str | None = Field(default=None, max_length=100)
    byte_size: int | None = Field(default=None, ge=1, le=10 * 1024 * 1024)

    @model_validator(mode="after")
    def _validate_license_use(self):
        return self
