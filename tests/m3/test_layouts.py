from datetime import datetime, timezone

import pytest

from pptmaker.assets.models import AssetRecord
from pptmaker.blueprint.models import ChartData, ChartSeries
from pptmaker.m3.design import PRESETS
from pptmaker.m3.layouts import CANVAS_H, CANVAS_W, layout_page
from pptmaker.research.contracts import FactRecord
from tests.blueprint.factories import blueprint


PAGE_TYPES = [
    "cover", "contents", "section", "conclusion", "text", "image_text",
    "cards", "comparison", "timeline", "process", "architecture",
    "data_chart", "case", "quote", "interaction", "qa", "ending",
]


def _fact():
    return FactRecord(
        id="fact-1",
        project_id="p1",
        statement="Verified result",
        source_url="https://example.com/report",
        source_title="Report",
        site_name="Example",
        accessed_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )


def _asset(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"image")
    return AssetRecord(
        id="asset-1",
        project_id="p1",
        blueprint_version=1,
        page_id="p1",
        provider="openverse",
        original_url="https://images.example/full.png",
        landing_url="https://example.com/work",
        thumbnail_url="https://images.example/thumb.png",
        creator="Alice",
        license_name="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        license_status="REUSABLE",
        license_mode="STRICT",
        attribution="Alice / CC BY 4.0",
        width=1600,
        height=900,
        accessed_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
        status="APPROVED",
        local_path=str(image),
        content_hash="a" * 64,
        mime_type="image/png",
        byte_size=5,
    )


@pytest.mark.parametrize("page_type", PAGE_TYPES)
def test_every_formal_page_type_stays_in_canvas(page_type, tmp_path):
    deck = blueprint(page_count=1)
    page = deck.pages[0].model_copy(
        update={
            "page_type": page_type,
            "supporting_points": ["Point one", "Point two", "Point three"],
        }
    )
    assets = []
    if page_type == "image_text":
        page = page.model_copy(
            update={
                "visual": page.visual.model_copy(update={"kind": "photo"}),
                "asset_ids": ["asset-1"],
            }
        )
        assets = [_asset(tmp_path)]
    if page_type == "data_chart":
        page = page.model_copy(
            update={
                "visual": page.visual.model_copy(
                    update={
                        "kind": "chart",
                        "chart_type": "column",
                        "chart_data": ChartData(
                            categories=["A", "B"],
                            series=[ChartSeries(name="Value", values=[1, 2])],
                        ),
                    }
                )
            }
        )
    spec = layout_page(
        page,
        deck.bible,
        PRESETS["business"].model_copy(update={"project_id": "p1"}),
        [_fact()],
        assets,
    )

    assert spec.page_type == page_type
    assert any(
        item.type == "text" and page.conclusion_title in item.text
        for item in spec.elements
    )
    for item in spec.elements:
        assert item.x >= 0.5
        assert item.y >= 0.35
        assert item.x + item.width <= CANVAS_W - 0.5 + 1e-6
        assert item.y + item.height <= CANVAS_H - 0.35 + 1e-6
        if hasattr(item, "font_size"):
            assert item.font_size >= 18
    assert not any(item.type == "image_placeholder" for item in spec.elements)


def test_layout_library_has_multiple_visual_silhouettes(tmp_path):
    deck = blueprint(page_count=1)
    design = PRESETS["business"].model_copy(update={"project_id": "p1"})
    signatures = set()
    for page_type in PAGE_TYPES:
        page = deck.pages[0].model_copy(update={"page_type": page_type})
        spec = layout_page(page, deck.bible, design, [], [])
        signatures.add(
            tuple(
                (item.type, round(item.x, 1), round(item.y, 1))
                for item in spec.elements
            )
        )
    assert len(signatures) >= 6
