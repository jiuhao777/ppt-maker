from datetime import datetime, timezone
from pathlib import Path

from pptmaker.assets.curator import AssetCurator
from pptmaker.assets.downloader import InvalidImage, VerifiedImage
from pptmaker.assets.models import AssetCandidate
from pptmaker.assets.repository import AssetRepository
from tests.blueprint.factories import blueprint


def candidate(index, license_status="REUSABLE"):
    return AssetCandidate(
        id=f"source-{index}",
        provider="openverse",
        original_url=f"https://images.example/{index}.jpg",
        landing_url=f"https://example/{index}",
        thumbnail_url=f"https://images.example/{index}-thumb.jpg",
        creator="Author",
        license_name="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        license_status=license_status,
        attribution="Author / CC BY 4.0",
        width=1600,
        height=900,
    )


class Search:
    def __init__(self, records):
        self.records = records
        self.calls = []

    def search(self, query, count):
        self.calls.append((query, count))
        return self.records


def downloader(record, destination, resolver):
    path = Path(destination) / f"{record.id}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"verified")
    return VerifiedImage(
        path=path,
        content_hash="a" * 64,
        mime_type="image/jpeg",
        byte_size=8,
        width=800,
        height=450,
    )


def image_blueprint():
    item = blueprint(page_count=1)
    page = item.pages[0].model_copy(
        update={
            "visual": item.pages[0].visual.model_copy(
                update={"kind": "photo"}
            ),
            "asset_search_query": "smart factory",
        }
    )
    return item.model_copy(update={"pages": [page]})


def test_curator_does_not_search_non_image_pages(tmp_path):
    search = Search([candidate(1)])
    result = AssetCurator(
        search,
        AssetRepository(tmp_path / "db.sqlite"),
        tmp_path / "assets",
        downloader=downloader,
        clock=lambda: datetime(2026, 7, 27, tzinfo=timezone.utc),
    ).curate("p1", blueprint(page_count=1), "STRICT")

    assert search.calls == []
    assert result.candidate_counts == {}


def test_curator_filters_strict_licenses_and_caps_verified_candidates(tmp_path):
    search = Search(
        [candidate(0, "RESTRICTED"), *[candidate(i) for i in range(1, 6)]]
    )
    repository = AssetRepository(tmp_path / "db.sqlite")

    result = AssetCurator(
        search,
        repository,
        tmp_path / "assets",
        downloader=downloader,
        clock=lambda: datetime(2026, 7, 27, tzinfo=timezone.utc),
    ).curate("p1", image_blueprint(), "STRICT")

    records = repository.list_for_blueprint("p1", 1, "p1")
    assert result.candidate_counts == {"p1": 3}
    assert len(records) == 3
    assert all(item.license_status == "REUSABLE" for item in records)


def test_curator_continues_after_invalid_image(tmp_path):
    calls = 0

    def flaky(record, destination, resolver):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise InvalidImage("decode failed")
        return downloader(record, destination, resolver)

    repository = AssetRepository(tmp_path / "db.sqlite")
    result = AssetCurator(
        Search([candidate(1), candidate(2)]),
        repository,
        tmp_path / "assets",
        downloader=flaky,
    ).curate("p1", image_blueprint(), "STRICT")

    assert result.candidate_counts == {"p1": 1}
    assert result.failures == {"p1": "some candidates failed verification"}
    assert repository.list_errors("p1", 1) == result.failures
