from pydantic import ValidationError
import pytest

from pptmaker.m3.models import (
    BulletElement,
    ColorPalette,
    ContentPlan,
    DesignPlan,
    FontSet,
    ImagePlaceholder,
    RectShape,
    SlideContent,
    SlideElement,
    SlideSpec,
    TableBlock,
    TextElement,
)


class TestCoreContracts:
    def test_content_plan_carries_schema_version_one(self):
        slide = SlideContent(
            page_id="p1", title="T", body_paragraphs=[],
            bullet_points=[], source_references=[],
        )
        plan = ContentPlan(project_id="p1", outline_version=1, slides=[slide])
        assert plan.schema_version == 1

    def test_design_plan_carries_schema_version_one(self):
        plan = DesignPlan(
            project_id="p1",
            preset="business",
            palette=ColorPalette(
                primary="#1F4E79",
                secondary="#5B9BD5",
                accent="#C59B27",
                background="#FFFFFF",
                text_primary="#1A1A1A",
                text_secondary="#666666",
            ),
            fonts=FontSet(
                title_zh="微软雅黑",
                body_zh="微软雅黑",
                title_en="Arial",
                body_en="Arial",
                title_size=30,
                subtitle_size=20,
                body_size=16,
            ),
            style_notes="测试风格",
        )
        assert plan.schema_version == 1

    def test_slide_spec_elements_are_discriminated(self):
        text = TextElement(
            type="text",
            text="标题",
            x=1.0,
            y=1.0,
            width=10.0,
            height=1.0,
            font_size=30,
            font_name="Arial",
            color="#000000",
            bold=True,
        )
        bullet = BulletElement(
            type="bullet",
            items=["要点1", "要点2"],
            x=1.0,
            y=2.0,
            width=10.0,
            height=2.0,
            font_size=16,
            font_name="Arial",
            color="#333333",
        )
        spec = SlideSpec(
            page_id="p1",
            order=1,
            page_type="content",
            background_color="#FFFFFF",
            elements=[text, bullet],
        )
        assert spec.elements[0].type == "text"
        assert spec.elements[1].type == "bullet"


class TestColorPalette:
    def test_rejects_invalid_hex(self):
        with pytest.raises(ValidationError):
            ColorPalette(
                primary="not-a-color",
                secondary="#fff",
                accent="#000",
                background="#fff",
                text_primary="#000",
                text_secondary="#666",
            )

    def test_accepts_valid_hex(self):
        palette = ColorPalette(
            primary="#1F4E79",
            secondary="#5B9BD5",
            accent="#C59B27",
            background="#FFFFFF",
            text_primary="#1A1A1A",
            text_secondary="#666666",
        )
        assert palette.primary == "#1F4E79"


class TestFontSet:
    def test_rejects_small_title_size(self):
        with pytest.raises(ValidationError):
            FontSet(
                title_zh="Arial",
                body_zh="Arial",
                title_en="Arial",
                body_en="Arial",
                title_size=10,
                subtitle_size=20,
                body_size=16,
            )

    def test_accepts_valid_sizes(self):
        fonts = FontSet(
            title_zh="Arial",
            body_zh="Arial",
            title_en="Arial",
            body_en="Arial",
            title_size=30,
            subtitle_size=20,
            body_size=16,
        )
        assert fonts.title_size == 30


class TestSlideContent:
    def test_optional_fields_default_none(self):
        content = SlideContent(
            page_id="p1",
            title="标题",
            body_paragraphs=["正文段落"],
            bullet_points=[],
            source_references=[],
        )
        assert content.subtitle is None
        assert content.key_number is None
        assert content.key_number_label is None
        assert content.image_suggestion is None

    def test_title_max_length(self):
        with pytest.raises(ValidationError):
            SlideContent(page_id="p1", title="x" * 201, body_paragraphs=[], bullet_points=[], source_references=[])


class TestSlideSpecConstraints:
    def test_page_order_must_be_positive(self):
        with pytest.raises(ValidationError):
            SlideSpec(
                page_id="p1",
                order=0,
                page_type="content",
                background_color="#FFFFFF",
                elements=[],
            )

    def test_page_type_must_be_valid(self):
        with pytest.raises(ValidationError):
            SlideSpec(
                page_id="p1",
                order=1,
                page_type="invalid_type",
                background_color="#FFFFFF",
                elements=[],
            )

    def test_elements_capped_at_reasonable_max(self):
        elements = [
            TextElement(
                type="text",
                text=f"e{i}",
                x=1.0,
                y=1.0,
                width=1.0,
                height=1.0,
                font_size=14,
                font_name="Arial",
                color="#000000",
            )
            for i in range(50)
        ]
        with pytest.raises(ValidationError):
            SlideSpec(
                page_id="p1",
                order=1,
                page_type="content",
                background_color="#FFFFFF",
                elements=elements,
            )
