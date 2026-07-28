from pathlib import Path

from pptmaker.assets.models import AssetRecord
from pptmaker.blueprint.models import DeckBlueprint
from pptmaker.m3.layouts import layout_page
from pptmaker.m3.models import (
    ColorPalette,
    DesignPlan,
    FontSet,
    SlideSpec,
)
from pptmaker.m3.quality import (
    QualityRepairError,
    inspect_specs,
    repair_specs,
)
from pptmaker.research.contracts import FactRecord


class BlueprintCompileError(ValueError):
    pass


def design_from_blueprint(blueprint: DeckBlueprint) -> DesignPlan:
    bible = blueprint.bible
    accents = bible.accent_colors
    neutrals = bible.neutral_colors
    background = next(
        (
            color
            for color in neutrals
            if color.lower() in {"#ffffff", "#f5f5f5", "#f7f7f7", "#fafafa"}
        ),
        "#FFFFFF",
    )
    text_primary = next(
        (
            color
            for color in neutrals
            if color.lower() not in {
                "#ffffff", "#f5f5f5", "#f7f7f7", "#fafafa"
            }
        ),
        "#1A1A1A",
    )
    return DesignPlan(
        project_id=blueprint.project_id,
        preset="blueprint",
        palette=ColorPalette(
            primary=bible.primary_color,
            secondary=accents[1] if len(accents) > 1 else "#E8EEF7",
            accent=accents[0] if accents else bible.primary_color,
            background=background,
            text_primary=text_primary,
            text_secondary="#666666",
        ),
        fonts=FontSet(
            title_zh=bible.title_font,
            body_zh=bible.body_font,
            title_en=bible.title_font,
            body_en=bible.body_font,
            title_size=35,
            subtitle_size=24,
            body_size=18,
        ),
        style_notes=bible.image_style,
    )


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
        selected_slots = [
            slot for slot in page.asset_slots if slot.selected_asset_id
        ]
        for slot in selected_slots:
            asset_id = slot.selected_asset_id
            asset = asset_map.get(asset_id)
            if (
                asset is None
                or asset.page_id != page.page_id
                or asset.slot_id != slot.slot_id
                or not asset.local_path
                or not Path(asset.local_path).is_file()
            ):
                if slot.required:
                    raise BlueprintCompileError(
                        "page references an invalid required asset"
                    )
                continue
            page_assets.append(asset)
        for asset_id in page.asset_ids:
            if asset_id in {item.id for item in page_assets}:
                continue
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
            and not page.asset_slots
        ):
            raise BlueprintCompileError(
                "image page requires an approved local asset"
            )
        if page.page_type == "data_chart" and (
            page.visual.kind != "chart"
            or page.visual.chart_data is None
        ):
            raise BlueprintCompileError(
                "data chart page requires structured chart data"
            )

        if page.visual.kind == "chart":
            data = page.visual.chart_data
            chart_type = (page.visual.chart_type or "").lower()
            if data is None:
                raise BlueprintCompileError("chart page has no chart data")
            if chart_type not in {
                "column", "bar", "line", "pie", "doughnut"
            }:
                raise BlueprintCompileError("chart type is invalid")
        spec = layout_page(
            page,
            blueprint.bible,
            design,
            [fact_map[item] for item in page.fact_ids],
            page_assets,
        )
        represented_paths = {
            element.path
            for element in spec.elements
            if element.type == "image"
        }
        if any(
            item.local_path not in represented_paths
            for item in page_assets
        ):
            raise BlueprintCompileError(
                "page layout does not represent its approved asset"
            )
        specs.append(spec)
    report = inspect_specs(specs)
    if report.passed:
        return specs
    try:
        repaired = repair_specs(specs, report)
    except QualityRepairError as exc:
        raise BlueprintCompileError(
            "slide quality check failed"
        ) from exc
    if not inspect_specs(repaired).passed:
        raise BlueprintCompileError("slide quality check failed")
    return repaired
