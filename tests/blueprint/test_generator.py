from datetime import datetime, timezone

import pytest

from pptmaker.blueprint.generator import (
    BlueprintPageBatch,
    BlueprintSkeleton,
    InvalidBlueprint,
    generate_blueprint,
)
from pptmaker.blueprint.models import BlueprintSection, DeckBible
from pptmaker.m2.models import (
    DeckOutline,
    OutlinePage,
    RequirementBrief,
    RequirementField,
)
from pptmaker.m3.design import PRESETS
from pptmaker.research.contracts import FactRecord
from tests.blueprint.factories import page


def outline() -> DeckOutline:
    return DeckOutline(
        project_id="p1",
        version=1,
        status="APPROVED",
        narrative="从痛点到价值",
        target_slides=3,
        pages=[
            OutlinePage(
                id=f"p{i}",
                order=i,
                section="价值",
                title=f"第{i}页结论",
                objective="说明价值",
            )
            for i in range(1, 4)
        ],
    )


def brief() -> RequirementBrief:
    return RequirementBrief(
        project_id="p1",
        scenario=RequirementField(value="产品路演", confidence=1),
        audience=RequirementField(value="投资人", confidence=1),
        purpose=RequirementField(value="获得投资", confidence=1),
    )


def design():
    return PRESETS["business"].model_copy(update={"project_id": "p1"})


def fact(*, excluded: bool = False, statement: str = "效率提升30%"):
    return FactRecord(
        id="fact-1",
        project_id="p1",
        statement=statement,
        source_title="测试来源",
        source_url="https://example.com/source",
        site_name="示例",
        accessed_at=datetime.now(timezone.utc),
        excluded=excluded,
    )


def skeleton() -> BlueprintSkeleton:
    return BlueprintSkeleton(
        bible=DeckBible(
            scenario="产品路演",
            audience="投资人",
            objective="获得投资",
            narrative_framework="SCQA",
            narrative="从痛点到产品价值",
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
                title="价值",
                audience_question="为什么值得投资？",
                conclusion="产品显著提升效率",
                page_ids=["p1", "p2", "p3"],
            )
        ],
    )


class QueueModel:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def generate(self, schema, system, user, api_key):
        self.calls.append(
            {"schema": schema, "system": system, "user": user}
        )
        return self.results.pop(0)


def test_generator_uses_skeleton_then_page_batches():
    model = QueueModel(
        [
            skeleton(),
            BlueprintPageBatch(pages=[page("p1", 1), page("p2", 2)]),
            BlueprintPageBatch(pages=[page("p3", 3)]),
        ]
    )

    result = generate_blueprint(
        outline(),
        brief(),
        [fact()],
        design(),
        model,
        "TEST_KEY",
        batch_size=2,
    )

    assert len(model.calls) == 3
    assert [item.page_id for item in result.pages] == ["p1", "p2", "p3"]
    assert result.status == "DRAFT"


def test_generator_never_sends_excluded_facts():
    model = QueueModel(
        [
            skeleton(),
            BlueprintPageBatch(
                pages=[page("p1", 1), page("p2", 2), page("p3", 3)]
            ),
        ]
    )

    generate_blueprint(
        outline(),
        brief(),
        [fact(excluded=True, statement="private statement")],
        design(),
        model,
        "TEST_KEY",
    )

    assert all("private statement" not in call["user"] for call in model.calls)


def test_generator_rejects_missing_or_extra_pages():
    model = QueueModel(
        [
            skeleton(),
            BlueprintPageBatch(
                pages=[page("p1", 1), page("unexpected", 2)]
            ),
        ]
    )

    with pytest.raises(InvalidBlueprint):
        generate_blueprint(
            outline(),
            brief(),
            [],
            design(),
            model,
            "TEST_KEY",
            batch_size=2,
        )


def test_generator_requires_approved_outline():
    draft = outline().model_copy(update={"status": "DRAFT"})

    with pytest.raises(InvalidBlueprint):
        generate_blueprint(
            draft,
            brief(),
            [],
            design(),
            QueueModel([]),
            "TEST_KEY",
        )
