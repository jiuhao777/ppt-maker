from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ── Design Tokens ──────────────────────────────────────────────

class ColorPalette(BaseModel):
    primary: str = Field(min_length=4, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")
    secondary: str = Field(min_length=4, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")
    accent: str = Field(min_length=4, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")
    background: str = Field(min_length=4, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")
    text_primary: str = Field(min_length=4, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")
    text_secondary: str = Field(min_length=4, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")


class FontSet(BaseModel):
    title_zh: str = Field(default="微软雅黑", min_length=1, max_length=100)
    body_zh: str = Field(default="微软雅黑", min_length=1, max_length=100)
    title_en: str = Field(default="Arial", min_length=1, max_length=100)
    body_en: str = Field(default="Arial", min_length=1, max_length=100)
    title_size: int = Field(default=30, ge=14, le=72)
    subtitle_size: int = Field(default=20, ge=12, le=48)
    body_size: int = Field(default=16, ge=10, le=36)


# ── Planner Outputs ────────────────────────────────────────────

class SlideContent(BaseModel):
    page_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=200)
    body_paragraphs: list[str] = Field(default_factory=list, max_length=20)
    bullet_points: list[str] = Field(default_factory=list, max_length=20)
    key_number: str | None = Field(default=None, max_length=50)
    key_number_label: str | None = Field(default=None, max_length=50)
    image_suggestion: str | None = Field(default=None, max_length=500)
    source_references: list[str] = Field(default_factory=list, max_length=20)


class ContentPlan(BaseModel):
    schema_version: Literal[1] = 1
    project_id: str
    outline_version: int = Field(ge=1)
    slides: list[SlideContent] = Field(min_length=1, max_length=100)


class DesignPlan(BaseModel):
    schema_version: Literal[1] = 1
    project_id: str
    preset: str = Field(default="custom", min_length=1, max_length=50)
    palette: ColorPalette
    fonts: FontSet = Field(default_factory=FontSet)
    style_notes: str = Field(default="", max_length=500)


# ── Slide DSL Elements ─────────────────────────────────────────

class TextElement(BaseModel):
    type: Literal["text"] = "text"
    text: str = Field(min_length=1, max_length=5_000)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    font_size: int = Field(ge=8, le=96)
    font_name: str = Field(min_length=1, max_length=100)
    bold: bool = False
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class BulletElement(BaseModel):
    type: Literal["bullet"] = "bullet"
    items: list[str] = Field(min_length=1, max_length=30)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    font_size: int = Field(ge=8, le=96)
    font_name: str = Field(min_length=1, max_length=100)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class ImagePlaceholder(BaseModel):
    type: Literal["image_placeholder"] = "image_placeholder"
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    description: str = Field(default="[图片区域]", max_length=500)


class RectShape(BaseModel):
    type: Literal["rect"] = "rect"
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    fill_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class TableBlock(BaseModel):
    type: Literal["table"] = "table"
    rows: list[list[str]] = Field(min_length=1, max_length=30)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    font_size: int = Field(ge=8, le=36)


SlideElement = TextElement | BulletElement | ImagePlaceholder | RectShape | TableBlock

_VALID_TYPES = frozenset(
    {"cover", "contents", "section", "content", "ending"}
)


class SlideSpec(BaseModel):
    page_id: str = Field(min_length=1)
    order: int = Field(ge=1)
    page_type: str = Field(min_length=1)
    background_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    elements: list[SlideElement] = Field(default_factory=list, max_length=30)

    @field_validator("page_type")
    @classmethod
    def _check_page_type(cls, value: str) -> str:
        if value not in _VALID_TYPES:
            raise ValueError(
                f"invalid page_type: {value!r}; "
                f"expected one of {sorted(_VALID_TYPES)}"
            )
        return value
