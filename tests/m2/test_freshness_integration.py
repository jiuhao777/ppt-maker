from datetime import datetime, timezone

import pytest

from pptmaker.m2.interview import RequirementExtraction
from pptmaker.m2.models import (
    DeckOutline,
    DeckOutlineDraft,
    OutlinePage,
    RequirementBrief,
    RequirementField,
)
from pptmaker.m2.repository import M2Repository
from pptmaker.m2.outlines import generate_outline
from pptmaker.research.contracts import (
    FactRecord,
    FreshnessDecision,
    ResearchRun,
    SearchResult,
)
from pptmaker.projects import ProjectCreate, ProjectRepository
from pptmaker.ui.m2_workspace import WorkspaceServices
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


def test_auto_without_key_requires_explicit_stale_approval(tmp_path):
    repository = ResearchRepository(tmp_path / "research.db")
    service = FreshnessService(
        FakeSearch(),
        repository,
        clock=lambda: NOW,
    )

    run = service.run(
        "p1",
        "AUTO",
        extraction("中国大模型现状", True),
        "",
    )

    assert run.status == "PLANNED"
    assert run.requires_user_action is True

    accepted = service.accept_stale(run)

    assert accepted.status == "SKIPPED_NO_KEY"
    assert accepted.requires_user_action is False
    assert repository.get_latest_run("p1").status == "SKIPPED_NO_KEY"


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
    assert run.requires_user_action is True
    assert search.queries == []


def test_new_freshness_decision_clears_previous_facts(tmp_path):
    repository = ResearchRepository(tmp_path / "research.db")
    repository.replace_facts(
        "p1",
        [
            FactRecord(
                project_id="p1",
                statement="旧主题事实",
                source_url="https://example.com/old",
                source_title="旧来源",
                site_name="Example",
                accessed_at=NOW,
            )
        ],
    )

    FreshnessService(FakeSearch(), repository).plan(
        "p1", "AUTO", extraction("新的时效主题", True)
    )

    assert repository.list_facts("p1") == []


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


def test_workspace_searches_before_outline_and_passes_active_facts(
    monkeypatch, tmp_path
):
    projects = ProjectRepository(tmp_path / "pptmaker.db")
    project = projects.create(ProjectCreate(name="Fresh"))
    m2 = M2Repository(projects.path)
    brief = extraction("中国最先进的大模型", True).brief.model_copy(
        update={"project_id": project.id}
    )
    m2.save_brief(brief)
    research = ResearchRepository(projects.path)
    pending = FreshnessService(FakeSearch(), research).plan(
        project.id,
        "AUTO",
        RequirementExtraction(
            brief=brief,
            ai_freshness=FreshnessDecision(
                requires_web=True,
                reason="模型信息会变化",
                freshness_level="HIGH",
            ),
        ),
    )
    events = []
    fact = FactRecord(
        project_id=project.id,
        statement="当前代表模型包括 DeepSeek。",
        source_url="https://example.com/source",
        source_title="来源",
        site_name="Example",
        accessed_at=NOW,
    )

    def run_search(service, *args, **kwargs):
        events.append("search")
        service.repository.replace_facts(project.id, [fact])
        completed = pending.model_copy(
            update={
                "status": "COMPLETED",
                "fact_ids": [fact.id],
                "requires_user_action": False,
            }
        )
        service.repository.save_run(completed)
        return completed

    def make_outline(_brief, _chunks, _model, _key, *, facts):
        events.append("outline")
        assert [item.id for item in facts] == [fact.id]
        return DeckOutline(
            project_id=project.id,
            version=1,
            status="DRAFT",
            narrative="现状",
            target_slides=1,
            pages=[
                OutlinePage(
                    order=1,
                    section="现状",
                    title="DeepSeek 进入代表模型",
                    objective="说明最新格局",
                    source_locations=["https://example.com/source"],
                )
            ],
        )

    monkeypatch.setattr(FreshnessService, "run", run_search)
    monkeypatch.setattr(
        "pptmaker.ui.m2_workspace.generate_outline", make_outline
    )
    monkeypatch.setattr(
        "pptmaker.ui.m2_workspace._provider", lambda: object()
    )
    monkeypatch.setattr(
        "pptmaker.ui.m2_workspace.st.session_state",
        {"search_freshness": "oneYear"},
    )

    WorkspaceServices(
        project.id, projects, m2, "MODEL_KEY", "BOCHA_KEY"
    ).generate_outline(project.id)

    assert events == ["search", "outline"]
