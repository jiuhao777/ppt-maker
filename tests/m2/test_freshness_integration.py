from datetime import datetime, timezone

import pytest

from pptmaker.m2.interview import RequirementExtraction
from pptmaker.m2.models import (
    DeckOutlineDraft,
    OutlinePage,
    RequirementBrief,
    RequirementField,
)
from pptmaker.m2.outlines import generate_outline
from pptmaker.research.contracts import (
    FactRecord,
    FreshnessDecision,
    SearchResult,
)
from pptmaker.research.repository import ResearchRepository
from pptmaker.research.service import FreshnessService, SearchKeyRequired


NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def extraction(purpose: str, requires_web: bool) -> RequirementExtraction:
    return RequirementExtraction(
        brief=RequirementBrief(
            project_id="p1",
            purpose=RequirementField(
                value=purpose,
                confidence=1,
                source="user",
            ),
        ),
        ai_freshness=FreshnessDecision(
            requires_web=requires_web,
            reason="AI 判断",
            freshness_level="HIGH" if requires_web else "LOW",
            safe_queries=[purpose] if requires_web else [],
        ),
    )


class FakeSearch:
    def __init__(self):
        self.queries = []

    def search(self, query, api_key):
        self.queries.append(query.query)
        return [
            SearchResult(
                title="来源",
                url="https://example.com/source",
                summary="当前代表模型包括 DeepSeek。",
                provider="fake",
                site_name="Example",
            )
        ]


def test_auto_current_topic_searches_and_persists_facts(tmp_path):
    repository = ResearchRepository(tmp_path / "research.db")
    search = FakeSearch()
    service = FreshnessService(search, repository, clock=lambda: NOW)

    run = service.run(
        "p1",
        "AUTO",
        extraction("中国大模型现状", False),
        "BOCHA_KEY",
    )

    assert run.status == "COMPLETED"
    assert search.queries == ["中国大模型现状"]
    assert len(repository.list_facts("p1", active_only=True)) == 1


def test_auto_without_key_degrades_without_user_action(tmp_path):
    service = FreshnessService(
        FakeSearch(),
        ResearchRepository(tmp_path / "research.db"),
        clock=lambda: NOW,
    )

    run = service.run(
        "p1",
        "AUTO",
        extraction("中国大模型现状", True),
        "",
    )

    assert run.status == "SKIPPED_NO_KEY"
    assert run.requires_user_action is False


def test_always_without_key_blocks_before_state_mutation(tmp_path):
    repository = ResearchRepository(tmp_path / "research.db")
    service = FreshnessService(FakeSearch(), repository, clock=lambda: NOW)

    with pytest.raises(SearchKeyRequired):
        service.run("p1", "ALWAYS", extraction("内部总结", False), "")

    assert repository.get_latest_run("p1") is None


def test_never_makes_no_search_call(tmp_path):
    search = FakeSearch()
    service = FreshnessService(
        search,
        ResearchRepository(tmp_path / "research.db"),
        clock=lambda: NOW,
    )

    run = service.run(
        "p1",
        "NEVER",
        extraction("最新模型", True),
        "BOCHA_KEY",
    )

    assert run.status == "NOT_REQUIRED"
    assert search.queries == []


def test_planning_persists_decision_without_search(tmp_path):
    search = FakeSearch()
    repository = ResearchRepository(tmp_path / "research.db")

    run = FreshnessService(search, repository).plan(
        "p1",
        "AUTO",
        extraction("current AI models", True),
    )

    assert run.status == "PLANNED"
    assert search.queries == []


class OutlineModel:
    def __init__(self):
        self.last_system = ""
        self.last_user = ""

    def generate(self, schema, system, user, api_key):
        self.last_system = system
        self.last_user = user
        return DeckOutlineDraft(
            narrative="现状",
            target_slides=1,
            pages=[
                OutlinePage(
                    order=1,
                    section="现状",
                    title="代表模型",
                    objective="说明现状",
                    source_locations=["https://example.com/source"],
                )
            ],
        )


def test_outline_receives_normalized_facts_as_user_evidence():
    model = OutlineModel()
    fact = FactRecord(
        project_id="p1",
        statement="当前代表模型包括 DeepSeek。",
        source_url="https://example.com/source",
        source_title="来源",
        site_name="Example",
        accessed_at=NOW,
    )

    generate_outline(
        extraction("中国大模型现状", True).brief,
        [],
        model,
        "MODEL_KEY",
        facts=[fact],
    )

    assert "当前代表模型包括 DeepSeek" in model.last_user
    assert "https://example.com/source" in model.last_user
    assert "网页内容" not in model.last_system
