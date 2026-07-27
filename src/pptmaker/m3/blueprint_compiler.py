from pathlib import Path

from pptmaker.assets.models import AssetRecord
from pptmaker.blueprint.models import DeckBlueprint
from pptmaker.m3.models import (
    BulletElement,
    ChartElement,
    DesignPlan,
    ImageElement,
    SlideSpec,
    TextElement,
)
from pptmaker.research.contracts import FactRecord


class BlueprintCompileError(ValueError):
    pass


_CHART_TYPES = {"column", "bar", "line", "pie", "doughnut"}


def compile_blueprint(
    blueprint: DeckBlueprint,
    facts: list[FactRecord],
    assets: list[AssetRecord],
    design: DesignPlan,
) -> list[SlideSpec]:
    if blueprint.status != "APPROVED":
        raise BlueprintCompileError("blueprint must be approved")
    if design.project_id != blueprint.project_id:
        raise BlueprintCompileError("design project does not match")

    fact_map = {
        item.id: item
        for item in facts
        if item.project_id == blueprint.project_id and not item.excluded
    }
    asset_map = {
        item.id: item
        for item in assets
        if item.project_id == blueprint.project_id
        and item.blueprint_version == blueprint.version
        and item.status == "APPROVED"
    }
    specs = []
    for page in sorted(blueprint.pages, key=lambda item: item.order):
        if set(page.fact_ids) - set(fact_map):
            raise BlueprintCompileError("page references an invalid fact")
        page_assets = []
        for asset_id in page.asset_ids:
            asset = asset_map.get(asset_id)
            if (
                asset is None
                or asset.page_id != page.page_id
                or not asset.local_path
                or not Path(asset.local_path).is_file()
            ):
                raise BlueprintCompileError(
                    "page references an invalid asset"
                )
            page_assets.append(asset)
        if (
            page.visual.kind in {"photo", "illustration"}
            and not page_assets
        ):
            raise BlueprintCompileError(
                "image page requires an approved local asset"
            )

        elements = [
            TextElement(
                text=page.conclusion_title,
                x=0.7,
                y=0.5,
                width=11.9,
                height=0.8,
                font_size=max(32, design.fonts.title_size),
                font_name=design.fonts.title_zh,
                bold=True,
                color=design.palette.text_primary,
            )
        ]
        if page.supporting_points:
            elements.append(
                BulletElement(
                    items=page.supporting_points,
                    x=0.8,
                    y=1.6,
                    width=5.5 if page_assets else 11.5,
                    height=4.8,
                    font_size=max(18, design.fonts.body_size),
                    font_name=design.fonts.body_zh,
                    color=design.palette.text_primary,
                )
            )
        if page_assets:
            elements.append(
                ImageElement(
                    path=page_assets[0].local_path,
                    x=7.0,
                    y=1.5,
                    width=5.6,
                    height=4.8,
                )
            )
        if page.visual.kind == "chart":
            data = page.visual.chart_data
            chart_type = (page.visual.chart_type or "").lower()
            if data is None:
                raise BlueprintCompileError("chart page has no chart data")
            if chart_type not in _CHART_TYPES:
                raise BlueprintCompileError("chart type is invalid")
            elements.append(
                ChartElement(
                    chart_type=chart_type,
                    categories=data.categories,
                    series={
                        item.name: [float(value) for value in item.values]
                        for item in data.series
                    },
                    x=5.4,
                    y=1.6,
                    width=7.2,
                    height=4.8,
                )
            )
        sources = [
            f"{fact_map[item].source_title} · "
            f"{fact_map[item].source_url}"
            for item in page.fact_ids
        ]
        sources.extend(
            f"{item.attribution or item.creator or '作者未知'} · "
            f"{item.landing_url}"
            for item in page_assets
        )
        specs.append(
            SlideSpec(
                page_id=page.page_id,
                order=page.order,
                page_type=page.page_type,
                background_color=design.palette.background,
                elements=elements,
                speaker_notes=page.speaker_notes,
                source_references=sources,
                transition=(
                    "fade"
                    if blueprint.bible.animation_level == "simple"
                    else "none"
                ),
            )
        )
    return specs
