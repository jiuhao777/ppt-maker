from datetime import date, datetime
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class LicenseStatus(str, Enum):
    REUSABLE = "reusable"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    snippet: str = Field(default="", max_length=10_000)
    summary: str = Field(default="", max_length=20_000)
    site_name: str = Field(default="未知来源", max_length=200)
    published_at: datetime | None = None
    provider: str = Field(min_length=1)


WebPolicy = Literal["AUTO", "ALWAYS", "NEVER"]
FreshnessLevel = Literal["LOW", "MEDIUM", "HIGH"]


class FreshnessDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    requires_web: bool
    reason: str = Field(min_length=1, max_length=500)
    freshness_level: FreshnessLevel
    verification_topics: list[str] = Field(default_factory=list, max_length=5)
    safe_queries: list[str] = Field(default_factory=list, max_length=5)


class SearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    freshness: Literal[
        "noLimit", "oneDay", "oneWeek", "oneMonth", "oneYear"
    ] = "oneYear"
    count: int = Field(default=5, ge=1, le=10)


class FactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    statement: str = Field(min_length=1, max_length=2_000)
    source_url: HttpUrl
    source_title: str = Field(min_length=1, max_length=500)
    site_name: str = Field(min_length=1, max_length=200)
    published_at: datetime | None = None
    accessed_at: datetime
    excluded: bool = False


class ResearchRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    project_id: str
    policy: WebPolicy
    decision: FreshnessDecision
    status: Literal[
        "PLANNED", "NOT_REQUIRED", "SKIPPED_NO_KEY", "COMPLETED", "FAILED"
    ]
    fact_ids: list[str] = Field(default_factory=list)
    safe_error_type: str | None = Field(default=None, max_length=100)
    requires_user_action: bool = False


class AssetCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    source_page: HttpUrl
    author: str | None = None
    license_name: str | None = None
    license_url: HttpUrl | None = None
    license_status: LicenseStatus
    accessed_at: date
