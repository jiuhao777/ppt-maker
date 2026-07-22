from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class LicenseStatus(str, Enum):
    REUSABLE = "reusable"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    url: HttpUrl
    snippet: str
    provider: str = Field(min_length=1)


class AssetCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    source_page: HttpUrl
    author: str | None = None
    license_name: str | None = None
    license_url: HttpUrl | None = None
    license_status: LicenseStatus
    accessed_at: date
