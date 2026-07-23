from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


BusinessState = Literal[
    "COLLECTING_REQUIREMENTS",
    "WAITING_FOR_USER",
    "GENERATING_OUTLINE",
    "OUTLINE_REVIEW",
    "OUTLINE_APPROVED",
    "FAILED_RECOVERABLE",
    "FAILED_FINAL",
]
OutlineStatus = Literal["DRAFT", "APPROVED", "SUPERSEDED"]
MaterialStatus = Literal["parsed", "unrecognized", "rejected", "failed"]
ResearchMaterialType = Literal["fact", "data", "case", "image", "quote"]
TaskType = Literal[
    "work_report",
    "project_report",
    "pitch",
    "thesis",
    "teaching",
    "data_report",
    "event",
    "custom",
]
CreationMethod = Literal[
    "GENERATED",
    "MANUAL_EDIT",
    "AI_GLOBAL_REWORK",
    "AI_LOCAL_REWORK",
    "RESTORED",
]
ReworkMode = Literal["global", "local"]


class RequirementField(BaseModel):
    value: str | int | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    source: str | None = None
    assumed: bool = False


class RequirementBrief(BaseModel):
    schema_version: Literal[1] = 1
    project_id: str
    purpose: RequirementField = Field(default_factory=RequirementField)
    audience: RequirementField = Field(default_factory=RequirementField)
    scenario: RequirementField = Field(default_factory=RequirementField)
    duration_minutes: RequirementField = Field(default_factory=RequirementField)
    target_slides: RequirementField = Field(default_factory=RequirementField)
    language: RequirementField = Field(default_factory=RequirementField)
    style: RequirementField = Field(default_factory=RequirementField)
    priorities: RequirementField = Field(default_factory=RequirementField)
    source_boundary: RequirementField = Field(default_factory=RequirementField)
    quality_preference: RequirementField = Field(default_factory=RequirementField)
    task_type: TaskType = "custom"
    special_requirements: dict[str, RequirementField] = Field(default_factory=dict)


class InterviewQuestion(BaseModel):
    field: str
    text: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(default_factory=list, max_length=4)
    allow_unknown: Literal[True] = True


class ConversationTurn(BaseModel):
    role: Literal["user", "agent"]
    content: str = Field(min_length=1, max_length=20_000)
    field: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MaterialChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    source_name: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=1_000_000)


class MaterialIngestResult(BaseModel):
    status: MaterialStatus
    chunks: list[MaterialChunk] = Field(default_factory=list)
    warning: str | None = Field(default=None, max_length=500)


class GapCandidate(BaseModel):
    field: str
    score: float
    blocking: bool


class OutlineGap(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    material_type: ResearchMaterialType
    priority: Literal["high", "medium", "low"]
    search_hint: str = Field(default="", max_length=500)


class OutlinePage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    order: int = Field(ge=1)
    section: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=500)
    key_points: list[str] = Field(default_factory=list, max_length=10)
    page_type: str = Field(default="content", max_length=100)
    source_locations: list[str] = Field(default_factory=list, max_length=100)
    gaps: list[OutlineGap] = Field(default_factory=list, max_length=20)


class DeckOutlineDraft(BaseModel):
    narrative: str = Field(min_length=1, max_length=2_000)
    target_slides: int = Field(ge=1, le=100)
    pages: list[OutlinePage] = Field(min_length=1, max_length=100)


class DeckOutline(DeckOutlineDraft):
    schema_version: Literal[1] = 1
    project_id: str
    version: int = Field(ge=1)
    status: OutlineStatus
    parent_version: int | None = Field(default=None, ge=1)
    creation_method: CreationMethod = "GENERATED"
    change_summary: str = Field(default="", max_length=2_000)


class ReworkRequest(BaseModel):
    mode: ReworkMode
    feedback: str = Field(min_length=1, max_length=2_000)
    selected_page_ids: list[str] = Field(default_factory=list, max_length=100)


class ReworkImpact(BaseModel):
    mode: ReworkMode
    feedback: str = Field(min_length=1, max_length=2_000)
    impacted_page_ids: list[str] = Field(min_length=1, max_length=100)
    reasons: dict[str, str]
    requirement_updates: dict[str, str] = Field(default_factory=dict)
    refresh_research_tasks: bool


class ResearchTask(BaseModel):
    schema_version: Literal[1] = 1
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    outline_version: int = Field(ge=1)
    question: str = Field(min_length=1, max_length=500)
    page_id: str
    related_page_ids: list[str] = Field(default_factory=list, max_length=100)
    material_type: ResearchMaterialType
    priority: Literal["high", "medium", "low"]
    search_hint: str = Field(default="", max_length=500)
    status: Literal["pending"] = "pending"


class ReflectionResult(BaseModel):
    passed: bool
    defects: list[str] = Field(default_factory=list)


class OutlineDiff(BaseModel):
    added_page_ids: list[str] = Field(default_factory=list)
    deleted_page_ids: list[str] = Field(default_factory=list)
    moved_page_ids: list[str] = Field(default_factory=list)
    title_changes: dict[str, tuple[str, str]] = Field(default_factory=dict)
