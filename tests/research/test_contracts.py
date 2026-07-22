from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from pptmaker.m0.search_runner import read_records, run_queries, summarize_records
from pptmaker.research.contracts import AssetCandidate, LicenseStatus, SearchResult


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
