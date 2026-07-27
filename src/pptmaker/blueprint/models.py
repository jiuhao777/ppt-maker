from typing import Literal

from pydantic import BaseModel, Field, model_validator


BlueprintStatus = Literal["DRAFT", "APPROVED", "SUPERSEDED"]
PageType = Literal[
    "cover",
    "contents",
    "section",
    "conclusion",
    "text",
    "image_text",
    "cards",
    "comparison",
    "timeline",
    "process",
    "architecture",
    "data_chart",
    "case",
    "quote",
    "interaction",
    "qa",
    "ending",
]
VisualKind = Literal[
    "none",
    "chart",
    "diagram",
    "photo",
    "illustration",
    "icons",
    "cards",
]


class DeckBible(BaseModel):
    schema_version: Literal[1] = 1
    scenario: str = Field(min_length=1, max_length=200)
    audience: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1, max_length=300)
    narrative_framework: str = Field(min_length=1, max_length=100)
    narrative: str = Field(min_length=1, max_length=1_000)
    action: str = Field(default="", max_length=300)
    terminology: dict[str, str] = Field(default_factory=dict, max_length=100)
    forbidden_content: list[str] = Field(default_factory=list, max_length=50)
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_colors: list[str] = Field(default_factory=list, max_length=2)
    neutral_colors: list[str] = Field(default_factory=list, max_length=4)
    title_font: str = Field(min_length=1, max_length=100)
    body_font: str = Field(min_length=1, max_length=100)
    extra_font: str | None = Field(default=None, max_length=100)
    image_style: str = Field(default="", max_length=300)
    icon_style: str = Field(default="", max_length=200)
    footer: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def _limit_fonts(self):
        fonts = {self.title_font, self.body_font}
        if self.extra_font:
            fonts.add(self.extra_font)
        if len(fonts) > 2:
            raise ValueError("deck may use at most two fonts")
        return self


class VisualPlan(BaseModel):
    kind: VisualKind
    layout: str = Field(min_length=1, max_length=100)
    ratio: str = Field(default="", max_length=50)
    alignment: Literal["left", "center", "right"] = "left"
    description: str = Field(default="", max_length=500)
    chart_type: str | None = Field(default=None, max_length=50)
    highlights: list[str] = Field(default_factory=list, max_length=2)


class BlueprintPage(BaseModel):
    page_id: str = Field(min_length=1)
    order: int = Field(ge=1, le=100)
    page_type: PageType
    purpose: str = Field(min_length=1, max_length=500)
    conclusion_title: str = Field(min_length=1, max_length=100)
    primary_message: str = Field(min_length=1, max_length=500)
    supporting_points: list[str] = Field(default_factory=list, max_length=3)
    detail: str = Field(default="", max_length=1_000)
    speaker_notes: str = Field(default="", max_length=5_000)
    forbidden_content: list[str] = Field(default_factory=list, max_length=20)
    previous_bridge: str = Field(default="", max_length=300)
    next_bridge: str = Field(default="", max_length=300)
    visual: VisualPlan
    fact_ids: list[str] = Field(default_factory=list, max_length=50)
    asset_search_query: str = Field(default="", max_length=500)
    asset_ids: list[str] = Field(default_factory=list, max_length=20)
    estimated_seconds: int = Field(default=60, ge=10, le=600)
    density: Literal["light", "medium", "heavy"] = "medium"
    memory_anchor: str = Field(default="", max_length=200)


class BlueprintSection(BaseModel):
    section_id: str = Field(min_length=1)
    order: int = Field(ge=1, le=20)
    title: str = Field(min_length=1, max_length=200)
    audience_question: str = Field(min_length=1, max_length=500)
    conclusion: str = Field(min_length=1, max_length=500)
    relation_to_previous: str = Field(default="", max_length=300)
    page_ids: list[str] = Field(min_length=1, max_length=50)


class BlueprintDraft(BaseModel):
    bible: DeckBible
    sections: list[BlueprintSection] = Field(min_length=1, max_length=20)
    pages: list[BlueprintPage] = Field(min_length=1, max_length=100)


class DeckBlueprint(BlueprintDraft):
    schema_version: Literal[1] = 1
    project_id: str
    outline_version: int = Field(ge=1)
    version: int = Field(ge=1)
    status: BlueprintStatus
    parent_version: int | None = Field(default=None, ge=1)
    change_summary: str = Field(default="", max_length=1_000)


class BlueprintReview(BaseModel):
    passed: bool
    defects: list[str] = Field(default_factory=list)
