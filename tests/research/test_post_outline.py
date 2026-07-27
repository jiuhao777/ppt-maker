from datetime import datetime, timezone

import pytest

from pptmaker.m2.models import (
    DeckOutline,
    OutlineGap,
    OutlinePage,
)
from pptmaker.research.contracts import FreshnessDecision, SearchResult
from pptmaker.research.post_outline import PostOutlineResearch
from pptmaker.research.repository import ResearchRepository
from pptmaker.research.service import SearchKeyRequired


NOW = datetime(2026, 7, 27, tzinfo=timezone.utc)


class Search:
    def __init__(self):
        self.queries = []

    def search(self, query, api_key):
        self.queries.append(query.query)
        return [
            SearchResult(
                title="Source",
                url="https://example.com/source",
                summary="Verified fact",
                provider="fake",
            )
        ]


def outline(status="APPROVED"):
    return DeckOutline(
        project_id="p1",
        version=1,
        status=status,
        narrative="AI market",
        target_slides=1,
        pages=[
            OutlinePage(
                id="page-1",
                order=1,
                section="Market",
                title="Market is growing",
                objective="Explain growth",
                gaps=[
                    OutlineGap(
                        question="What is the latest market size?",
                        search_hint="2026 AI market size",
                        material_type="data",
                        priority="high",
                    )
                ],
            )
        ],
    )


def decision():
    return FreshnessDecision(
        requires_web=True,
        reason="current data",
        freshness_level="HIGH",
    )


def test_research_uses_approved_outline_gap_queries(tmp_path):
    search = Search()
    repository = ResearchRepository(tmp_path / "db.sqlite")

    run = PostOutlineResearch(
        search, repository, clock=lambda: NOW
    ).run("p1", outline(), "AUTO", decision(), "KEY")

    assert run.status == "COMPLETED"
    assert search.queries == ["2026 AI market size"]
    assert len(repository.list_facts("p1")) == 1


def test_research_rejects_unapproved_outline(tmp_path):
    service = PostOutlineResearch(
        Search(), ResearchRepository(tmp_path / "db.sqlite")
    )
    with pytest.raises(ValueError, match="approved"):
        service.run("p1", outline("DRAFT"), "AUTO", decision(), "KEY")


def test_always_without_key_does_not_mutate_repository(tmp_path):
    repository = ResearchRepository(tmp_path / "db.sqlite")
    service = PostOutlineResearch(Search(), repository)

    with pytest.raises(SearchKeyRequired):
        service.run("p1", outline(), "ALWAYS", decision(), "")

    assert repository.get_latest_run("p1") is None
