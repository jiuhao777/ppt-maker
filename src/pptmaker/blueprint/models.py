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
LayoutElementKind = Literal[
    "title",
    "subtitle",
    "body",
    "chart",
    "image",
    "source",
    "footer",
    "page_number",
]
AssetRole = Literal[
    "background",
    "hero",
    "logo",
    "photo",
    "screenshot",
    "illustration",
    "icon",
    "case",
    "decorative",
]


class ChartSeries(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    values: list[float] = Field(min_length=1, max_length=30)


class ChartData(BaseModel):
    categories: list[str] = Field(min_length=1, max_length=30)
    series: list[ChartSeries] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def _matching_lengths(self):
        if any(
            len(item.values) != len(self.categories)
            for item in self.series
        ):
            raise ValueError("chart series must match category count")
        return self


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
    animation_level: Literal["none", "simple"] = "simple"

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
    chart_data: ChartData | None = None
    highlights: list[str] = Field(default_factory=list, max_length=2)


class LayoutRegion(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside_canvas(self):
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("layout region must stay inside canvas")
        return self


class LayoutElementPlan(BaseModel):
    element_id: str = Field(min_length=1, max_length=100)
    kind: LayoutElementKind
    region: LayoutRegion
    z_index: int = Field(default=0, ge=0, le=100)
    alignment: Literal["left", "center", "right"] = "left"
    font_size: int | None = Field(default=None, ge=10, le=72)
    color_token: str = Field(default="text_primary", max_length=50)
    content_ref: str = Field(min_length=1, max_length=100)
    fit: Literal["cover", "contain"] | None = None


class AssetSlot(BaseModel):
    slot_id: str = Field(min_length=1, max_length=100)
    role: AssetRole
    subject: str = Field(min_length=1, max_length=300)
    search_query: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=500)
    required: bool = False
    region: LayoutRegion = Field(
        default_factory=lambda: LayoutRegion(
            x=0.55, y=0.2, width=0.4, height=0.6
        )
    )
    fit: Literal["cover", "contain"] = "cover"
    z_index: int = Field(default=0, ge=0, le=100)
    fallback: Literal[
        "no_image", "icon", "text", "simplified_layout"
    ] = "simplified_layout"
    selected_asset_id: str | None = Field(default=None, max_length=200)


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
    layout_elements: list[LayoutElementPlan] = Field(default_factory=list)
    asset_slots: list[AssetSlot] = Field(default_factory=list, max_length=4)
    asset_search_query: str = Field(default="", max_length=500)
    asset_ids: list[str] = Field(default_factory=list, max_length=20)
    estimated_seconds: int = Field(default=60, ge=10, le=600)
    density: Literal["light", "medium", "heavy"] = "medium"
    memory_anchor: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def _validate_layout_references(self):
        slot_ids = [item.slot_id for item in self.asset_slots]
        element_ids = [item.element_id for item in self.layout_elements]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("asset slot ids must be unique")
        if len(element_ids) != len(set(element_ids)):
            raise ValueError("layout element ids must be unique")
        image_refs = {
            item.content_ref
            for item in self.layout_elements
            if item.kind == "image"
        }
        if image_refs - set(slot_ids):
            raise ValueError("image element references an unknown asset slot")
        return self


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
    schema_version: Literal[2] = 2
    project_id: str
    outline_version: int = Field(ge=1)
    version: int = Field(ge=1)
    status: BlueprintStatus
    parent_version: int | None = Field(default=None, ge=1)
    change_summary: str = Field(default="", max_length=1_000)


class BlueprintReview(BaseModel):
    passed: bool
    defects: list[str] = Field(default_factory=list)
