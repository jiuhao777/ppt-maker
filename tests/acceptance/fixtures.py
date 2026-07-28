from datetime import datetime, timezone

from PIL import Image

from pptmaker.assets.models import AssetRecord
from pptmaker.blueprint.models import (
    BlueprintPage,
    BlueprintSection,
    ChartData,
    ChartSeries,
    VisualPlan,
)
from pptmaker.research.contracts import FactRecord
from tests.blueprint.factories import blueprint


PAGE_TYPES = (
    "cover",
    "section",
    "cards",
    "comparison",
    "timeline",
    "process",
    "data_chart",
    "image_text",
    "quote",
    "ending",
)


def acceptance_inputs(tmp_path):
    pages = []
    for order, page_type in enumerate(PAGE_TYPES, start=1):
        visual = VisualPlan(kind="none", layout=page_type)
        fact_ids = []
        asset_ids = []
        if page_type == "data_chart":
            visual = VisualPlan(
                kind="chart",
                layout="chart",
                chart_type="column",
                chart_data=ChartData(
                    categories=["2025", "2026"],
                    series=[ChartSeries(name="采用率", values=[42, 68])],
                ),
            )
            fact_ids = ["fact-1"]
        elif page_type == "image_text":
            visual = VisualPlan(kind="photo", layout="image_right")
            asset_ids = ["asset-1"]
        pages.append(
            BlueprintPage(
                page_id=f"p{order}",
                order=order,
                page_type=page_type,
                purpose=f"完成第 {order} 页沟通目标",
                conclusion_title=f"第 {order} 页证明方案可落地",
                primary_message="核心信息清晰且可验证",
                supporting_points=["证据明确", "路径清晰", "行动具体"],
                speaker_notes="补充说明页面证据与衔接。",
                visual=visual,
                fact_ids=fact_ids,
                asset_ids=asset_ids,
            )
        )
    base = blueprint(page_count=1)
    deck = base.model_copy(
        update={
            "status": "APPROVED",
            "pages": pages,
            "sections": [
                BlueprintSection(
                    section_id="s1",
                    order=1,
                    title="完整叙事",
                    audience_question="为什么方案值得采用？",
                    conclusion="证据与行动形成闭环",
                    page_ids=[page.page_id for page in pages],
                )
            ],
        }
    )
    fact = FactRecord(
        id="fact-1",
        project_id=deck.project_id,
        statement="采用率从 42% 提升至 68%",
        source_url="https://example.com/report",
        source_title="公开研究报告",
        site_name="Example",
        accessed_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    image_path = tmp_path / "photo.png"
    Image.new("RGB", (1200, 800), "#165DFF").save(image_path)
    asset = AssetRecord(
        id="asset-1",
        project_id=deck.project_id,
        blueprint_version=deck.version,
        page_id="p8",
        provider="openverse",
        original_url="https://images.example/photo.png",
        landing_url="https://example.com/photo",
        thumbnail_url="https://images.example/thumb.png",
        creator="Example Author",
        license_name="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        license_status="REUSABLE",
        license_mode="STRICT",
        attribution="Example Author / CC BY 4.0",
        width=1200,
        height=800,
        accessed_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
        status="APPROVED",
        local_path=str(image_path),
        content_hash="a" * 64,
        mime_type="image/png",
        byte_size=image_path.stat().st_size,
    )
    return deck, [fact], [asset]
