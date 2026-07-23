import pytest
from pydantic import ValidationError

from pptmaker.m2.models import (
    DeckOutline,
    InterviewQuestion,
    OutlinePage,
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
