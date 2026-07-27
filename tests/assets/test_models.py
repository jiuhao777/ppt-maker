from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from pptmaker.assets.models import AssetRecord


def record(**updates) -> AssetRecord:
    values = {
        "id": "a1",
        "project_id": "p1",
        "blueprint_version": 1,
        "page_id": "page-1",
        "provider": "openverse",
        "original_url": "https://images.example/a.jpg",
        "landing_url": "https://example/a",
        "thumbnail_url": "https://images.example/a-thumb.jpg",
        "creator": "Author",
        "license_name": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "license_status": "REUSABLE",
        "license_mode": "STRICT",
        "attribution": "Author / CC BY 4.0",
        "width": 1600,
        "height": 900,
        "accessed_at": datetime(2026, 7, 27, tzinfo=timezone.utc),
    }
    values.update(updates)
    return AssetRecord(**values)


@pytest.mark.parametrize(("field", "value"), [("width", 0), ("height", 0)])
def test_asset_rejects_invalid_dimensions(field, value):
    with pytest.raises(ValidationError):
        record(**{field: value})


def test_loose_asset_requires_attribution_and_source():
    with pytest.raises(ValidationError):
        record(
            license_mode="LOOSE",
            license_status="UNKNOWN",
            creator=None,
            attribution="",
        )


def test_restricted_asset_cannot_be_approved_in_strict_mode():
    with pytest.raises(ValidationError):
        record(license_status="RESTRICTED", status="APPROVED")

