import json
from datetime import datetime, timezone

import pytest

from pptmaker.m3.models import ContentPlan, DesignPlan, SlideContent
from pptmaker.m3.content import plan_content
from pptmaker.m2.models import (
    DeckOutline,
    MaterialChunk,
    OutlinePage,
    RequirementBrief,
)
from pptmaker.research.contracts import FactRecord
from pptmaker.providers.structured import StructuredOutputError


def _brief(**kw) -> RequirementBrief:
    return RequirementBrief(project_id="p1", **kw)


def _design() -> DesignPlan:
    from pptmaker.m3.design import PRESETS
    return PRESETS["business"].model_copy(update={"project_id": "p1"})


def _outline(pages: int = 2) -> DeckOutline:
    return DeckOutline(
        project_id="p1", version=1, status="DRAFT",
        narrative="test", target_slides=pages,
        pages=[OutlinePage(id=f"p{i}", order=i, section="S", title=f"Page {i}",
                objective="test", key_points=[f"point {i}"]) for i in range(1, pages + 1)],
    )


def _fact(**kw) -> FactRecord:
    defaults = dict(project_id="p1", statement="s", source_title="t",
        source_url="https://example.com", site_name="ex",
        accessed_at=datetime.now(timezone.utc))
    return FactRecord(**(defaults | kw))


class TestContentPlan:
    def test_covers_all_outline_pages(self):
        class Fake:
            def generate(self, schema, system, prompt, api_key):
                return ContentPlan(project_id="p1", outline_version=1,
                    slides=[SlideContent(page_id=f"p{i}", title=f"Page {i}",
                        body_paragraphs=["text"], bullet_points=[], source_references=[])
                        for i in (1, 2)])
        plan = plan_content(_brief(), _outline(2), _design(), [], [], Fake(), "KEY")
        assert len(plan.slides) == 2

    def test_excluded_facts_not_in_prompt(self):
        class Fake:
            def generate(self, schema, system, prompt, api_key):
                self.last_prompt = prompt
                return ContentPlan(project_id="p1", outline_version=1,
                    slides=[SlideContent(page_id="p1", title="T", body_paragraphs=["ok"],
                        bullet_points=[], source_references=[])])
        model = Fake()
        plan_content(_brief(), _outline(1), _design(), [], [_fact(excluded=True)], model, "KEY")
        assert "secret" not in model.last_prompt

    def test_receives_design_context(self):
        class Fake:
            def generate(self, schema, system, prompt, api_key):
                self.last_prompt = prompt
                return ContentPlan(project_id="p1", outline_version=1,
                    slides=[SlideContent(page_id="p1", title="T", body_paragraphs=["x"],
                        bullet_points=[], source_references=[])])
        model = Fake()
        plan_content(_brief(), _outline(1), _design(), [], [], model, "KEY")
        assert "#1F4E79" in model.last_prompt  # business preset primary

    def test_retry_on_first_schema_failure(self):
        state = {"calls": 0}

        class Fake:
            def generate(self, schema, system, prompt, api_key):
                state["calls"] += 1
                if state["calls"] == 1:
                    raise StructuredOutputError("schema", "bad")
                return ContentPlan(project_id="p1", outline_version=1,
                    slides=[SlideContent(page_id="p1", title="T", body_paragraphs=["ok"],
                        bullet_points=[], source_references=[])])

        plan = plan_content(_brief(), _outline(1), _design(), [], [], Fake(), "KEY")
        assert state["calls"] == 2
        assert len(plan.slides) == 1

    def test_large_material_payload_remains_valid_json(self):
        class Fake:
            def generate(self, schema, system, prompt, api_key):
                self.last_prompt = prompt
                return ContentPlan(
                    project_id="p1",
                    outline_version=1,
                    slides=[
                        SlideContent(
                            page_id="p1",
                            title="T",
                            body_paragraphs=["ok"],
                        )
                    ],
                )

        model = Fake()
        chunk = MaterialChunk(
            project_id="p1",
            source_name="large.md",
            location="line 1",
            text="中" * 200_000,
        )

        plan_content(
            _brief(),
            _outline(1),
            _design(),
            [chunk],
            [],
            model,
            "KEY",
        )

        payload = json.loads(model.last_prompt)
        assert len(payload["materials"][0]["text"]) <= 3_000
