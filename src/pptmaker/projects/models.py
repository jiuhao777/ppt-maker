from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ExecutionState = Literal[
    "IDLE",
    "RUNNING",
    "WAITING_FOR_USER",
    "PAUSED",
    "CANCELLING",
    "CANCELLED",
    "FAILED_RECOVERABLE",
    "FAILED_FINAL",
    "COMPLETED",
]
ProjectBusinessState = Literal[
    "DRAFT",
    "COLLECTING_REQUIREMENTS",
    "WAITING_FOR_USER",
    "GENERATING_OUTLINE",
    "OUTLINE_REVIEW",
    "OUTLINE_APPROVED",
    "FAILED_RECOVERABLE",
    "FAILED_FINAL",
]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    last_provider_preset: str | None = Field(default=None, max_length=100)
    business_state: ProjectBusinessState = "DRAFT"
    execution_state: ExecutionState = "IDLE"
    execution_lease_expires_at: datetime | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    last_provider_preset: str | None = Field(default=None, max_length=100)
    business_state: ProjectBusinessState | None = None
    execution_state: ExecutionState | None = None
    execution_lease_expires_at: datetime | None = None


class Project(BaseModel):
    id: str
    name: str
    schema_version: int = 1
    business_state: ProjectBusinessState
    execution_state: ExecutionState
    execution_lease_expires_at: datetime | None = None
    last_provider_preset: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class ProjectExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    project_id: str
    name: str = Field(min_length=1, max_length=200)
    business_state: ProjectBusinessState
    execution_state: ExecutionState
    last_provider_preset: str | None = Field(default=None, max_length=100)
    created_at: datetime
    updated_at: datetime
