import pytest
from pydantic import ValidationError

from pptmaker.blueprint.models import BlueprintPage, DeckBible, VisualPlan


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
