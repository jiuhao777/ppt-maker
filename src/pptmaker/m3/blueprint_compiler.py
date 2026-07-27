from pathlib import Path

from pptmaker.assets.models import AssetRecord
from pptmaker.blueprint.models import DeckBlueprint
from pptmaker.m3.layouts import layout_page
from pptmaker.m3.models import DesignPlan, SlideSpec
from pptmaker.research.contracts import FactRecord


class BlueprintCompileError(ValueError):
    pass


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

        if page.visual.kind == "chart":
            data = page.visual.chart_data
            chart_type = (page.visual.chart_type or "").lower()
            if data is None:
                raise BlueprintCompileError("chart page has no chart data")
            if chart_type not in {
                "column", "bar", "line", "pie", "doughnut"
            }:
                raise BlueprintCompileError("chart type is invalid")
        specs.append(
            layout_page(
                page,
                blueprint.bible,
                design,
                [fact_map[item] for item in page.fact_ids],
                page_assets,
            )
        )
    return specs
