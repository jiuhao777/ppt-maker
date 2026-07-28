import json

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
    normalize_rework_draft,
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
        self.users = []
        self.systems = []

    def generate(self, schema, system, user, api_key):
        self.calls += 1
        self.systems.append(system)
        self.users.append(user)
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


def test_rework_analysis_payload_remains_valid_json():
    current = current_outline().model_copy(
        update={"narrative": "中" * 49_000}
    )
    impact = ReworkImpact(
        mode="global",
        feedback="更新",
        impacted_page_ids=["p1"],
        reasons={"p1": "关联"},
        refresh_research_tasks=False,
    )
    model = FakeModel([impact])

    analyze_rework(
        current,
        ReworkRequest(mode="global", feedback="中" * 2_000),
        model,
        "TEST_KEY",
    )

    json.loads(model.users[0])


def test_rework_retry_preserves_scope_instructions():
    current = current_outline()
    changed = current.pages[1].model_copy(
        update={"title": "过长" * 30}
    )
    invalid = DeckOutlineDraft(
        narrative=current.narrative,
        target_slides=3,
        pages=[current.pages[0], changed, current.pages[2]],
    )
    corrected = invalid.model_copy(
        update={
            "pages": [
                current.pages[0],
                changed.model_copy(update={"title": "更新后的方案"}),
                current.pages[2],
            ]
        }
    )
    impact = ReworkImpact(
        mode="local",
        feedback="只修改方案页",
        impacted_page_ids=["p2"],
        reasons={"p2": "用户指定"},
        refresh_research_tasks=False,
    )
    model = FakeModel([invalid, corrected])

    apply_rework(
        current,
        RequirementBrief(project_id="p1"),
        [],
        impact,
        model,
        "TEST_KEY",
    )

    retry_payload = json.loads(model.users[1])
    assert "影响范围外" in model.systems[1]
    assert retry_payload["impact"]["mode"] == "local"


def test_global_rework_normalizes_deterministic_quality_defects():
    current = current_outline()
    draft = DeckOutlineDraft(
        narrative="更新",
        target_slides=1,
        pages=[
            page("p1", 8, "效率提升30%", "说明结果").model_copy(
                update={"key_points": ["一", "二", "三", "四"]}
            ),
            page("p2", 9, "方案", "说明方案"),
            page("p3", 10, "行动", "说明行动"),
        ],
    )
    impact = ReworkImpact(
        mode="global",
        feedback="整体更新",
        impacted_page_ids=["p1", "p2", "p3"],
        reasons={"p1": "结果", "p2": "方案", "p3": "行动"},
        refresh_research_tasks=True,
    )

    normalized = normalize_rework_draft(current, draft, impact)

    assert normalized.target_slides == 3
    assert [item.order for item in normalized.pages] == [1, 2, 3]
    assert normalized.pages[0].key_points == ["一", "二", "三"]
    assert normalized.pages[0].gaps[0].material_type == "data"


def test_local_normalization_preserves_unaffected_pages_exactly():
    current = current_outline()
    changed = current.pages[1].model_copy(
        update={
            "title": "效率提升30%",
            "key_points": ["一", "二", "三", "四"],
        }
    )
    draft = DeckOutlineDraft(
        narrative=current.narrative,
        target_slides=99,
        pages=[current.pages[0], changed, current.pages[2]],
    )
    impact = ReworkImpact(
        mode="local",
        feedback="修改方案页",
        impacted_page_ids=["p2"],
        reasons={"p2": "用户指定"},
        refresh_research_tasks=True,
    )

    normalized = normalize_rework_draft(current, draft, impact)

    assert normalized.target_slides == current.target_slides
    assert normalized.pages[0] == current.pages[0]
    assert normalized.pages[2] == current.pages[2]
    assert len(normalized.pages[1].key_points) == 3
    assert normalized.pages[1].gaps
