from pathlib import Path

from pptx import Presentation
from pydantic import BaseModel

from pptmaker.blueprint.models import DeckBlueprint
from pptmaker.m3.models import SlideSpec
from pptmaker.m3.quality import inspect_specs


class ProductAcceptanceReport(BaseModel):
    requirement_coverage: float
    title_conclusion_rate: float
    severe_geometry_defects: int
    density_violation_rate: float
    public_fact_traceability: float
    asset_download_safety_rate: float
    file_reopens: bool
    passed: bool


def evaluate_deck(
    blueprint: DeckBlueprint,
    specs: list[SlideSpec],
    pptx_path: Path,
) -> ProductAcceptanceReport:
    by_id = {item.page_id: item for item in specs}
    page_count = len(blueprint.pages)
    covered = sum(
        page.page_id in by_id and bool(by_id[page.page_id].elements)
        for page in blueprint.pages
    )
    conclusion_titles = sum(
        _contains_title(by_id.get(page.page_id), page.conclusion_title)
        for page in blueprint.pages
    )
    report = inspect_specs(specs)
    severe = sum(
        item.code in {"out_of_bounds", "severe_overlap"}
        for item in report.defects
    )
    density_violations = sum(_body_characters(item) > 100 for item in specs)
    factual = [page for page in blueprint.pages if page.fact_ids]
    traceable = sum(
        bool(by_id.get(page.page_id) and by_id[page.page_id].source_references)
        for page in factual
    )
    image_specs = [
        item
        for item in specs
        if any(element.type == "image" for element in item.elements)
    ]
    safe_images = sum(
        all(
            Path(element.path).is_file()
            for element in item.elements
            if element.type == "image"
        )
        for item in image_specs
    )
    try:
        file_reopens = len(Presentation(str(pptx_path)).slides) == len(specs)
    except Exception:
        file_reopens = False

    coverage = _rate(covered, page_count)
    title_rate = _rate(conclusion_titles, page_count)
    density_rate = _rate(density_violations, len(specs))
    traceability = _rate(traceable, len(factual))
    image_safety = _rate(safe_images, len(image_specs))
    passed = (
        coverage >= 0.90
        and title_rate >= 0.90
        and severe == 0
        and density_rate <= 0.05
        and traceability >= 0.95
        and image_safety == 1.0
        and file_reopens
    )
    return ProductAcceptanceReport(
        requirement_coverage=coverage,
        title_conclusion_rate=title_rate,
        severe_geometry_defects=severe,
        density_violation_rate=density_rate,
        public_fact_traceability=traceability,
        asset_download_safety_rate=image_safety,
        file_reopens=file_reopens,
        passed=passed,
    )


def _contains_title(spec: SlideSpec | None, title: str) -> bool:
    return bool(
        spec
        and any(
            element.type == "text"
            and element.bold
            and element.text == title
            for element in spec.elements
        )
    )


def _body_characters(spec: SlideSpec) -> int:
    return sum(
        len(element.text)
        if element.type == "text" and not element.bold
        else sum(len(item) for item in element.items)
        if element.type == "bullet"
        else 0
        for element in spec.elements
    )


def _rate(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator
