from pptmaker.m2.models import (
    DeckOutline,
    DeckOutlineDraft,
    OutlineGap,
    OutlinePage,
    RequirementBrief,
    RequirementField,
)
from pptmaker.m2.outlines import (
    build_research_tasks,
    diff_outlines,
    generate_outline,
    reflect_outline,
)


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

    def generate(self, schema, system, user, api_key):
        self.calls += 1
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
