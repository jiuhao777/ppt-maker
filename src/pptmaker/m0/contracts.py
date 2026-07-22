from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProbeStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


class ProbeResult(BaseModel):
    name: str
    status: ProbeStatus
    metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
