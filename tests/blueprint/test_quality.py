from pptmaker.blueprint.quality import review_blueprint
from tests.blueprint.factories import blueprint


def test_review_accepts_valid_blueprint():
    assert review_blueprint(blueprint(), set()).passed


def test_review_rejects_missing_section_page_and_unknown_fact():
    candidate = blueprint()
    candidate.sections[0].page_ids.append("missing")
    candidate.pages[0].fact_ids = ["unknown"]

    review = review_blueprint(candidate, {"fact-1"})

    assert "section_page_missing" in review.defects
    assert "unknown_fact_reference" in review.defects


def test_review_rejects_four_heavy_pages_in_a_row():
    candidate = blueprint(page_count=4)
    candidate.pages = [
        item.model_copy(update={"density": "heavy"})
        for item in candidate.pages
    ]

    review = review_blueprint(candidate, set())

    assert "density_rhythm_invalid" in review.defects


def test_review_rejects_duplicate_titles_and_non_contiguous_order():
    candidate = blueprint()
    candidate.pages[1] = candidate.pages[1].model_copy(
        update={
            "order": 3,
            "conclusion_title": candidate.pages[0].conclusion_title,
        }
    )

    review = review_blueprint(candidate, set())

    assert "page_order_invalid" in review.defects
    assert "duplicate_titles" in review.defects
