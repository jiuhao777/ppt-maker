from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


IssueType = Literal[
    "overflow",
    "crowded",
    "weak_hierarchy",
    "irrelevant_image",
    "misalignment",
    "inconsistent_style",
]


class VisionIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: IssueType
    severity: Literal["low", "medium", "high"]
    region: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class VisionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slide_id: str = Field(min_length=1)
    issues: list[VisionIssue]
    overall_score: int = Field(ge=0, le=100)
