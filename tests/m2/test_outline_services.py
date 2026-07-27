import json

from pptmaker.m2.models import (
    DeckOutline,
    DeckOutlineDraft,
    MaterialChunk,
    OutlineGap,
    OutlinePage,
    RequirementBrief,
    RequirementField,
)
from pptmaker.m2.outlines import (
    build_research_tasks,
    deduplicate_research_tasks,
    diff_outlines,
    generate_outline,
    reflect_outline,
)
from pptmaker.m2.models import ResearchTask


def page(page_id, order, title, *, gaps=None, sources=None):
    return OutlinePage(
        id=page_id,
        order=order,
        section="Main",
        title=title,
        objective="Explain",
        gaps=gaps or [],
        source_locations=sources or [],
    )


def deck(*pages):
    return DeckOutline(
        project_id="p1",
        version=1,
        status="DRAFT",
        narrative="Story",
        target_slides=len(pages),
        pages=list(pages),
    )


def brief():
    return RequirementBrief(
        project_id="p1",
        purpose=RequirementField(value="Project update", confidence=1, source="user"),
        duration_minutes=RequirementField(value=10, confidence=1, source="user"),
        target_slides=RequirementField(value=5, confidence=1, source="user"),
    )


def test_reflection_detects_duplicate_pages_and_page_count():
    outline = deck(
        page("p1", 1, "Same"),
        page("p2", 2, " same "),
    )
    outline.target_slides = 3

    result = reflect_outline(brief(), outline)

    assert "duplicate_titles" in result.defects
    assert "page_count_mismatch" in result.defects
    assert result.passed is False


def test_every_unresolved_gap_becomes_research_task():
    outline = deck(
        page(
            "p1",
            1,
            "Market",
            gaps=[
                OutlineGap(
                    question="Need current market size",
                    material_type="data",
                    priority="high",
                )
            ],
        ),
        page(
            "p2",
            2,
            "Product",
            gaps=[
                OutlineGap(
                    question="Need product image",
                    material_type="image",
                    priority="medium",
                )
            ],
        ),
    )

    tasks = build_research_tasks(outline)

    assert {(task.page_id, task.material_type) for task in tasks} == {
        ("p1", "data"),
        ("p2", "image"),
    }


def test_diff_reports_add_delete_move_and_title_change():
    old = deck(page("p1", 1, "Old"), page("p2", 2, "Second"))
    new = deck(page("p2", 1, "Second"), page("p3", 2, "Third"))
    new.pages.append(page("p1", 3, "New"))
    new.target_slides = 3

    diff = diff_outlines(old, new)

    assert diff.added_page_ids == ["p3"]
    assert diff.deleted_page_ids == []
    assert diff.moved_page_ids == ["p2", "p1"]
    assert diff.title_changes["p1"] == ("Old", "New")


class FakeModel:
    def __init__(self, drafts):
        self.drafts = list(drafts)
        self.calls = 0
        self.users = []

    def generate(self, schema, system, user, api_key):
        self.calls += 1
        self.users.append(user)
        return self.drafts.pop(0)


def test_generation_runs_one_bounded_quality_correction():
    duplicate = DeckOutlineDraft(
        narrative="Story",
        target_slides=2,
        pages=[page("p1", 1, "Same"), page("p2", 2, "Same")],
    )
    corrected = duplicate.model_copy(
        update={
            "pages": [page("p1", 1, "Start"), page("p2", 2, "Finish")]
        }
    )
    model = FakeModel([duplicate, corrected])

    result = generate_outline(brief(), [], model, "TEST_KEY")

    assert [item.title for item in result.pages] == ["Start", "Finish"]
    assert model.calls == 2


def test_outline_prompt_is_valid_json_with_large_material():
    draft = DeckOutlineDraft(
        narrative="Story",
        target_slides=1,
        pages=[page("p1", 1, "Start")],
    )
    model = FakeModel([draft])
    chunk = MaterialChunk(
        project_id="p1",
        source_name="large.md",
        location="line 1",
        text="中" * 200_000,
    )

    generate_outline(brief(), [chunk], model, "TEST_KEY")

    payload = json.loads(model.users[0])
    assert len(payload["materials"][0]["text"]) <= 3_000


def research(question, material_type, page_id):
    return ResearchTask(
        project_id="p1",
        outline_version=1,
        question=question,
        page_id=page_id,
        material_type=material_type,
        priority="medium",
    )


def test_equivalent_research_gaps_merge_across_pages():
    merged = deduplicate_research_tasks([
        research("市场规模？", "data", "p1"),
        research("市场 规模", "data", "p2"),
    ])

    assert len(merged) == 1
    assert merged[0].related_page_ids == ["p1", "p2"]


def test_same_words_with_different_material_types_do_not_merge():
    tasks = [
        research("市场规模", "data", "p1"),
        research("市场规模", "image", "p1"),
    ]

    assert len(deduplicate_research_tasks(tasks)) == 2
