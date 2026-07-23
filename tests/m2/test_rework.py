import pytest

from pptmaker.m2.models import (
    DeckOutline,
    DeckOutlineDraft,
    OutlinePage,
    RequirementBrief,
    ReworkImpact,
    ReworkRequest,
)
from pptmaker.m2.rework import (
    InvalidRework,
    analyze_rework,
    apply_rework,
    validate_rework_scope,
)


def page(page_id, order, title, objective):
    return OutlinePage(
        id=page_id,
        order=order,
        section="Main",
        title=title,
        objective=objective,
    )


def current_outline():
    return DeckOutline(
        project_id="p1",
        version=1,
        status="DRAFT",
        narrative="制造业 AI 转型",
        target_slides=3,
        pages=[
            page("p1", 1, "制造业现状", "说明制造业挑战"),
            page("p2", 2, "制造业方案", "介绍制造业方案"),
            page("p3", 3, "下一步", "给出行动计划"),
        ],
    )


class FakeModel:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def generate(self, schema, system, user, api_key):
        self.calls += 1
        return self.results.pop(0)


def test_impact_analysis_rejects_unknown_page():
    current = current_outline()
    model = FakeModel([
        ReworkImpact(
            mode="local",
            feedback="修改方案",
            impacted_page_ids=["missing"],
            reasons={"missing": "关联"},
            refresh_research_tasks=True,
        )
    ])

    with pytest.raises(InvalidRework):
        analyze_rework(
            current,
            ReworkRequest(
                mode="local",
                feedback="修改方案",
                selected_page_ids=["p2"],
            ),
            model,
            "TEST_KEY",
        )


def test_global_industry_rework_removes_old_industry_everywhere():
    current = current_outline()
    draft = DeckOutlineDraft(
        narrative="服务业 AI 转型",
        target_slides=3,
        pages=[
            page("p1", 1, "服务业现状", "说明服务业挑战"),
            page("p2", 2, "服务业方案", "介绍服务业方案"),
            page("p3", 3, "下一步", "给出行动计划"),
        ],
    )
    impact = ReworkImpact(
        mode="global",
        feedback="制造业改为服务业",
        impacted_page_ids=["p1", "p2", "p3"],
        reasons={"p1": "行业", "p2": "行业", "p3": "行动"},
        refresh_research_tasks=True,
    )

    result = apply_rework(
        current,
        RequirementBrief(project_id="p1"),
        [],
        impact,
        FakeModel([draft]),
        "TEST_KEY",
    )

    assert "制造业" not in result.model_dump_json()
    assert "服务业" in result.model_dump_json()


def test_local_rework_preserves_unaffected_pages_exactly():
    current = current_outline()
    changed = current.pages[1].model_copy(
        update={"title": "服务方案", "objective": "更新方案"}
    )
    draft = DeckOutlineDraft(
        narrative=current.narrative,
        target_slides=3,
        pages=[current.pages[0], changed, current.pages[2]],
    )
    impact = ReworkImpact(
        mode="local",
        feedback="只修改方案页",
        impacted_page_ids=["p2"],
        reasons={"p2": "用户指定"},
        refresh_research_tasks=True,
    )

    result = apply_rework(
        current,
        RequirementBrief(project_id="p1"),
        [],
        impact,
        FakeModel([draft]),
        "TEST_KEY",
    )

    assert result.pages[0] == current.pages[0]
    assert result.pages[2] == current.pages[2]


def test_invalid_local_rework_is_rejected():
    current = current_outline()
    changed_outside_scope = current.pages[0].model_copy(
        update={"title": "Unexpected"}
    )
    draft = DeckOutlineDraft(
        narrative=current.narrative,
        target_slides=3,
        pages=[changed_outside_scope, current.pages[1], current.pages[2]],
    )
    impact = ReworkImpact(
        mode="local",
        feedback="只修改方案页",
        impacted_page_ids=["p2"],
        reasons={"p2": "用户指定"},
        refresh_research_tasks=False,
    )

    with pytest.raises(InvalidRework):
        validate_rework_scope(current, draft, impact)
