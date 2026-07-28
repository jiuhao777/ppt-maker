from datetime import datetime, timezone

import pytest

from pptmaker.assets.models import AssetRecord
from pptmaker.blueprint.models import ChartData, ChartSeries
from pptmaker.m3.blueprint_compiler import BlueprintCompileError, compile_blueprint
from pptmaker.m3.design import PRESETS
from pptmaker.research.contracts import FactRecord
from tests.blueprint.factories import blueprint


def fact(project_id="p1", excluded=False):
    return FactRecord(
        id="fact-1",
        project_id=project_id,
        statement="Revenue increased 30%",
        source_url="https://example.com/report",
        source_title="Annual report",
        site_name="Example",
        accessed_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
        excluded=excluded,
    )


def asset(path, **updates):
    values = {
        "id": "asset-1",
        "project_id": "p1",
        "blueprint_version": 1,
        "page_id": "p1",
        "provider": "openverse",
        "original_url": "https://images.example/full.jpg",
        "landing_url": "https://example.com/work",
        "thumbnail_url": "https://images.example/thumb.jpg",
        "creator": "Alice",
        "license_name": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "license_status": "REUSABLE",
        "license_mode": "STRICT",
        "attribution": "Alice / CC BY 4.0",
        "width": 1600,
        "height": 900,
        "accessed_at": datetime(2026, 7, 27, tzinfo=timezone.utc),
        "status": "APPROVED",
        "local_path": str(path),
        "content_hash": "a" * 64,
        "mime_type": "image/jpeg",
        "byte_size": 100,
    }
    values.update(updates)
    return AssetRecord(**values)


def approved_blueprint():
    item = blueprint(page_count=1)
    page = item.pages[0].model_copy(
        update={
            "fact_ids": ["fact-1"],
            "speaker_notes": "Explain the benchmark.",
        }
    )
    return item.model_copy(
        update={"status": "APPROVED", "pages": [page]}
    )


def design():
    return PRESETS["business"].model_copy(update={"project_id": "p1"})


def test_compiler_requires_approved_blueprint():
    with pytest.raises(BlueprintCompileError, match="approved"):
        compile_blueprint(blueprint(page_count=1), [], [], design())


def test_compiler_preserves_order_notes_sources_and_transition():
    specs = compile_blueprint(
        approved_blueprint(), [fact()], [], design()
    )

    assert [item.order for item in specs] == [1]
    assert specs[0].speaker_notes == "Explain the benchmark."
    assert specs[0].source_references == [
        "Annual report · https://example.com/report"
    ]
    assert specs[0].transition == "fade"
    assert any(
        element.type == "text"
        and element.text == approved_blueprint().pages[0].conclusion_title
        for element in specs[0].elements
    )


def test_compiler_rejects_excluded_or_cross_project_fact():
    with pytest.raises(BlueprintCompileError, match="fact"):
        compile_blueprint(
            approved_blueprint(), [fact(excluded=True)], [], design()
        )


def test_compiler_requires_bound_approved_local_image(tmp_path):
    item = approved_blueprint()
    page = item.pages[0].model_copy(
        update={
            "visual": item.pages[0].visual.model_copy(
                update={"kind": "photo"}
            ),
            "asset_ids": ["asset-1"],
        }
    )
    item = item.model_copy(update={"pages": [page]})

    with pytest.raises(BlueprintCompileError, match="asset"):
        compile_blueprint(item, [fact()], [], design())

    image_path = tmp_path / "image.jpg"
    image_path.write_bytes(b"verified")
    specs = compile_blueprint(
        item, [fact()], [asset(image_path)], design()
    )
    image = next(el for el in specs[0].elements if el.type == "image")
    assert image.path == str(image_path)
    assert any("Alice" in source for source in specs[0].source_references)


def test_compiler_emits_native_chart_data():
    item = approved_blueprint()
    page = item.pages[0].model_copy(
        update={
            "page_type": "data_chart",
            "visual": item.pages[0].visual.model_copy(
                update={
                    "kind": "chart",
                    "chart_type": "column",
                    "chart_data": ChartData(
                        categories=["2025", "2026"],
                        series=[
                            ChartSeries(name="Revenue", values=[10, 13])
                        ],
                    ),
                }
            ),
        }
    )
    specs = compile_blueprint(
        item.model_copy(update={"pages": [page]}),
        [fact()],
        [],
        design(),
    )

    chart = next(el for el in specs[0].elements if el.type == "chart")
    assert chart.series == {"Revenue": [10.0, 13.0]}


def test_data_chart_page_requires_structured_chart_data():
    item = approved_blueprint()
    page = item.pages[0].model_copy(update={"page_type": "data_chart"})

    with pytest.raises(BlueprintCompileError, match="structured"):
        compile_blueprint(
            item.model_copy(update={"pages": [page]}),
            [fact()],
            [],
            design(),
        )
