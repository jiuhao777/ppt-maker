import pytest
from pydantic import ValidationError

from pptmaker.m2.models import (
    DeckOutline,
    InterviewQuestion,
    OutlinePage,
    ReworkImpact,
    ReworkRequest,
    ResearchTask,
    RequirementBrief,
)


def test_core_contracts_have_schema_version_one():
    assert RequirementBrief(project_id="p1").schema_version == 1
    assert DeckOutline(
        project_id="p1",
        version=1,
        status="DRAFT",
        narrative="Main story",
        target_slides=1,
        pages=[
            OutlinePage(
                order=1,
                section="Intro",
                title="Why",
                objective="Frame",
            )
        ],
    ).schema_version == 1
    assert ResearchTask(
        project_id="p1",
        outline_version=1,
        question="What is the market size?",
        page_id="page-1",
        material_type="data",
        priority="high",
    ).schema_version == 1


def test_interview_question_requires_reason_and_unknown_path():
    with pytest.raises(ValidationError):
        InterviewQuestion(field="audience", text="Who?", reason="")

    question = InterviewQuestion(
        field="audience",
        text="Who?",
        reason="The audience determines the narrative.",
    )
    assert question.allow_unknown is True


def test_outline_page_ids_are_stable_and_unique():
    first = OutlinePage(
        order=1,
        section="Intro",
        title="First",
        objective="Open",
    )
    encoded = first.model_dump()
    restored = OutlinePage.model_validate(encoded)
    second = OutlinePage(
        order=2,
        section="Intro",
        title="Second",
        objective="Continue",
    )

    assert restored.id == first.id
    assert second.id != first.id


def test_interview_question_choices_are_bounded():
    question = InterviewQuestion(
        field="audience",
        text="主要给谁看？",
        reason="受众会影响内容深度。",
        options=["管理层", "客户"],
    )
    assert question.options == ["管理层", "客户"]

    with pytest.raises(ValidationError):
        InterviewQuestion(
            field="audience",
            text="主要给谁看？",
            reason="受众会影响内容深度。",
            options=["1", "2", "3", "4", "5"],
        )


def test_rework_contracts_require_feedback_and_impact():
    request = ReworkRequest(mode="global", feedback="制造业改为服务业")
    impact = ReworkImpact(
        mode="global",
        feedback=request.feedback,
        impacted_page_ids=["page-1"],
        reasons={"page-1": "行业变化"},
        requirement_updates={"purpose": "服务业 AI 转型"},
        refresh_research_tasks=True,
    )

    assert impact.impacted_page_ids == ["page-1"]
