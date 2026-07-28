import pytest
from pydantic import ValidationError

from pptmaker.blueprint.models import (
    AssetSlot,
    BlueprintPage,
    DeckBible,
    LayoutElementPlan,
    LayoutRegion,
    VisualPlan,
)


def test_page_rejects_more_than_three_supporting_points():
    with pytest.raises(ValidationError):
        BlueprintPage(
            page_id="p1",
            order=1,
            page_type="text",
            purpose="说明价值",
            conclusion_title="效率提升来自流程自动化",
            primary_message="自动化减少重复劳动",
            supporting_points=["一", "二", "三", "四"],
            visual=VisualPlan(kind="cards", layout="three_cards"),
        )


def test_deck_bible_rejects_more_than_two_fonts():
    with pytest.raises(ValidationError):
        DeckBible(
            scenario="路演",
            audience="投资人",
            objective="获得投资",
            narrative_framework="SCQA",
            narrative="从痛点到投资价值",
            primary_color="#165DFF",
            accent_colors=["#FF8800"],
            neutral_colors=["#111111", "#FFFFFF"],
            title_font="微软雅黑",
            body_font="思源黑体",
            extra_font="宋体",
        )


def test_visual_plan_limits_highlights_to_two():
    with pytest.raises(ValidationError):
        VisualPlan(
            kind="chart",
            layout="chart_right",
            highlights=["10%", "20%", "30%"],
        )


def _slot(slot_id: str) -> AssetSlot:
    return AssetSlot(
        slot_id=slot_id,
        role="photo",
        subject="办公场景",
        search_query="人工智能 办公",
        purpose="支撑页面结论",
        region=LayoutRegion(x=0.5, y=0.2, width=0.4, height=0.6),
    )


def test_page_allows_four_unique_asset_slots():
    source = BlueprintPage(
        page_id="p1",
        order=1,
        page_type="image_text",
        purpose="说明价值",
        conclusion_title="自动化显著提升效率",
        primary_message="自动化减少重复劳动",
        visual=VisualPlan(kind="photo", layout="image_right"),
        asset_slots=[_slot(f"image-{index}") for index in range(4)],
    )
    assert len(source.asset_slots) == 4


def test_page_rejects_five_asset_slots():
    with pytest.raises(ValidationError):
        BlueprintPage(
            page_id="p1",
            order=1,
            page_type="image_text",
            purpose="说明价值",
            conclusion_title="自动化显著提升效率",
            primary_message="自动化减少重复劳动",
            visual=VisualPlan(kind="photo", layout="image_right"),
            asset_slots=[_slot(f"image-{index}") for index in range(5)],
        )


def test_region_rejects_canvas_overflow():
    with pytest.raises(ValidationError):
        LayoutRegion(x=0.8, y=0.1, width=0.3, height=0.2)


def test_image_element_must_reference_a_real_slot():
    with pytest.raises(ValidationError):
        BlueprintPage(
            page_id="p1",
            order=1,
            page_type="image_text",
            purpose="说明价值",
            conclusion_title="自动化显著提升效率",
            primary_message="自动化减少重复劳动",
            visual=VisualPlan(kind="photo", layout="image_right"),
            layout_elements=[
                LayoutElementPlan(
                    element_id="image",
                    kind="image",
                    region=LayoutRegion(
                        x=0.5, y=0.2, width=0.4, height=0.6
                    ),
                    content_ref="missing",
                    fit="cover",
                )
            ],
        )
