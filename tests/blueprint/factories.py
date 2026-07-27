from pptmaker.blueprint.models import (
    BlueprintPage,
    BlueprintSection,
    DeckBible,
    DeckBlueprint,
    VisualPlan,
)


def page(page_id: str, order: int) -> BlueprintPage:
    return BlueprintPage(
        page_id=page_id,
        order=order,
        page_type="text",
        purpose="说明价值",
        conclusion_title=f"第{order}页结论",
        primary_message="自动化减少重复劳动",
        supporting_points=["效率提升", "错误减少"],
        visual=VisualPlan(kind="cards", layout="three_cards"),
    )


def blueprint(page_count: int = 3) -> DeckBlueprint:
    pages = [page(f"p{order}", order) for order in range(1, page_count + 1)]
    return DeckBlueprint(
        project_id="p1",
        outline_version=1,
        version=1,
        status="DRAFT",
        bible=DeckBible(
            scenario="产品路演",
            audience="投资人",
            objective="获得投资",
            narrative_framework="SCQA",
            narrative="从行业痛点到产品价值",
            action="进入尽调",
            primary_color="#165DFF",
            accent_colors=["#FF8800"],
            neutral_colors=["#111111", "#FFFFFF"],
            title_font="微软雅黑",
            body_font="微软雅黑",
        ),
        sections=[
            BlueprintSection(
                section_id="s1",
                order=1,
                title="核心价值",
                audience_question="为什么值得投资？",
                conclusion="产品可以显著提升效率",
                page_ids=[item.page_id for item in pages],
            )
        ],
        pages=pages,
    )
