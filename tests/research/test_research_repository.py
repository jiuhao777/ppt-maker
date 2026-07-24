from datetime import datetime, timezone

from pptmaker.research.contracts import (
    FactRecord,
    FreshnessDecision,
    ResearchRun,
)
from pptmaker.research.repository import ResearchRepository


NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def fact(fact_id: str) -> FactRecord:
    return FactRecord(
        id=fact_id,
        project_id="p1",
        statement=f"fact {fact_id}",
        source_url=f"https://example.com/{fact_id}",
        source_title=fact_id,
        site_name="Example",
        accessed_at=NOW,
    )


def test_facts_replace_atomically_and_exclusion_persists(tmp_path):
    repository = ResearchRepository(tmp_path / "research.db")
    repository.replace_facts("p1", [fact("a"), fact("b")])

    repository.exclude_fact("p1", "a")

    assert [item.id for item in repository.list_facts("p1")] == ["a", "b"]
    assert [item.id for item in repository.list_facts("p1", active_only=True)] == [
        "b"
    ]
    repository.replace_facts("p1", [fact("c")])
    assert [item.id for item in repository.list_facts("p1")] == ["c"]


def test_latest_research_run_round_trips_without_keys(tmp_path):
    repository = ResearchRepository(tmp_path / "research.db")
    run = ResearchRun(
        project_id="p1",
        policy="AUTO",
        decision=FreshnessDecision(
            requires_web=False,
            reason="无需联网",
            freshness_level="LOW",
        ),
        status="NOT_REQUIRED",
    )

    repository.save_run(run)

    restored = repository.get_latest_run("p1")
    assert restored == run
    assert "api_key" not in restored.model_dump_json()
