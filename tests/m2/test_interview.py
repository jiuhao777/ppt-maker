from pptmaker.m2.interview import (
    accept_unknown,
    extract_requirements,
    plan_next_question,
    rank_gaps,
    remaining_question_count,
)
from pptmaker.m2.models import MaterialChunk, RequirementBrief, RequirementField


def field(value, confidence=1.0, source="user"):
    return RequirementField(
        value=value,
        confidence=confidence,
        source=source,
    )


def complete_brief(**changes):
    values = {
        "project_id": "p1",
        "purpose": field("Project update"),
        "scenario": field("Leadership meeting"),
        "audience": field("Executives"),
        "target_slides": field(10),
        "priorities": field("Progress and risks"),
    }
    values.update(changes)
    return RequirementBrief(**values)


def test_known_information_is_not_asked_again():
    brief = complete_brief(scenario=RequirementField())

    question = plan_next_question(brief)

    assert question.field == "scenario"
    assert question.field != "audience"
    assert question.reason
    assert question.allow_unknown is True


def test_one_call_returns_at_most_one_question():
    question = plan_next_question(RequirementBrief(project_id="p1"))

    assert question is not None
    assert not isinstance(question, list)


def test_gap_ranking_uses_declared_business_priority():
    brief = complete_brief(
        scenario=RequirementField(),
        audience=RequirementField(),
    )

    gaps = rank_gaps(brief)

    assert [gap.field for gap in gaps[:2]] == ["scenario", "audience"]


def test_low_confidence_material_value_is_confirmed():
    brief = complete_brief(
        audience=field("Students", confidence=0.4, source="material")
    )

    assert plan_next_question(brief).field == "audience"


def test_unknown_answer_creates_marked_assumption():
    updated = accept_unknown(
        complete_brief(audience=RequirementField()),
        "audience",
        "暂按部门管理者作为主要受众，后续验证",
    )

    assert updated.audience.assumed is True
    assert updated.audience.confidence < 0.5
    assert updated.audience.source == "assumption"
    assert all(gap.field != "audience" for gap in rank_gaps(updated))


class FakeStructuredModel:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def generate(self, schema, system, user, api_key):
        self.calls += 1
        return self.result


def test_extraction_cannot_overwrite_user_confirmed_field():
    current = complete_brief()
    extracted = complete_brief(
        audience=field("Students", confidence=0.8, source="material")
    )
    model = FakeStructuredModel(extracted)

    merged = extract_requirements(
        "p1",
        [MaterialChunk(
            project_id="p1",
            source_name="brief.md",
            location="line:1",
            text="Audience may be students.",
        )],
        [],
        model,
        "TEST_KEY",
        current=current,
    )

    assert merged.audience.value == "Executives"
    assert merged.audience.source == "user"
    assert model.calls == 1


def test_pitch_and_thesis_receive_different_special_questions():
    pitch = complete_brief(task_type="pitch", special_requirements={})
    thesis = complete_brief(task_type="thesis", special_requirements={})

    assert plan_next_question(pitch).field == "special:funding_goal"
    assert plan_next_question(thesis).field == "special:research_method"


def test_question_count_never_exceeds_eight():
    brief = RequirementBrief(project_id="p1", task_type="pitch")
    fields = []
    while question := plan_next_question(brief):
        fields.append(question.field)
        brief = accept_unknown(brief, question.field, "待验证")

    assert 1 <= len(fields) <= 8
    assert len(fields) == len(set(fields))


def test_question_is_simple_and_has_choices():
    question = plan_next_question(
        complete_brief(audience=RequirementField())
    )

    assert len(question.text) <= 40
    assert 2 <= len(question.options) <= 4
    assert remaining_question_count(
        complete_brief(audience=RequirementField())
    ) >= 1
