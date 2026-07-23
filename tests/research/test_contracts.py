from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from pptmaker.m0.search_runner import read_records, run_queries, summarize_records
from pptmaker.research.contracts import (
    AssetCandidate,
    FactRecord,
    FreshnessDecision,
    LicenseStatus,
    ResearchRun,
    SearchQuery,
    SearchResult,
)


def test_asset_requires_source_url_and_access_date():
    with pytest.raises(ValidationError):
        AssetCandidate(
            url="https://example.com/a.jpg",
            license_status=LicenseStatus.UNKNOWN,
        )


def test_asset_preserves_provenance_and_license_url():
    asset = AssetCandidate(
        url="https://images.example.com/a.jpg",
        source_page="https://example.com/photo/a",
        author="Author",
        license_name="Example License",
        license_url="https://example.com/license",
        license_status=LicenseStatus.REUSABLE,
        accessed_at=date(2026, 7, 23),
    )
    assert str(asset.source_page) == "https://example.com/photo/a"


class FakeAdapter:
    name = "fake"

    def __init__(self):
        self.calls = 0

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        self.calls += 1
        if self.calls == 2:
            raise TimeoutError("fixture timeout")
        item = SearchResult(
            title="Example",
            url="https://example.com/source",
            snippet=query,
            provider=self.name,
        )
        return [item, item] if self.calls == 1 else [item]


def test_runner_retains_success_errors_and_duplicates(tmp_path: Path):
    output = tmp_path / "runs.jsonl"
    run_queries(FakeAdapter(), ["固定查询"], output, attempts=3)
    records = read_records(output)
    summary = summarize_records(records)

    assert len(records) == 3
    assert any(record["error"] for record in records)
    assert summary["runs"] == 3
    assert summary["error_rate"] > 0
    assert summary["duplicate_urls"] > 0


def test_freshness_contracts_are_strict_and_versioned():
    decision = FreshnessDecision(
        requires_web=True,
        reason="主题具有时效性",
        freshness_level="HIGH",
        verification_topics=["代表模型"],
        safe_queries=["中国 大模型 现状"],
    )

    assert decision.schema_version == 1
    with pytest.raises(ValidationError):
        FreshnessDecision.model_validate(
            {**decision.model_dump(), "api_key": "TEST_KEY"}
        )


def test_search_fact_and_run_contracts_contain_no_secret_fields():
    query = SearchQuery(query="中国大模型现状")
    fact = FactRecord(
        project_id="p1",
        statement="示例事实",
        source_url="https://example.com/source",
        source_title="来源",
        site_name="Example",
        accessed_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )
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

    assert query.count == 5
    assert fact.schema_version == 1
    assert run.schema_version == 1
    assert "api_key" not in run.model_dump_json()
