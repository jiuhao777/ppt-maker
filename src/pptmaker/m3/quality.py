from pathlib import Path

from pydantic import BaseModel, Field

from pptmaker.m3.models import SlideSpec


class SpecDefect(BaseModel):
    code: str
    page_id: str
    element_index: int | None = None


class SpecQualityReport(BaseModel):
    passed: bool
    defects: list[SpecDefect] = Field(default_factory=list)


class QualityRepairError(ValueError):
    pass


def inspect_specs(specs: list[SlideSpec]) -> SpecQualityReport:
    defects = []
    expected_orders = list(range(1, len(specs) + 1))
    if [item.order for item in specs] != expected_orders:
        defects.append(SpecDefect(code="page_order", page_id="deck"))
    titles = []
    for spec in specs:
        title = next(
            (
                item.text.strip().lower()
                for item in spec.elements
                if item.type == "text" and item.bold
            ),
            "",
        )
        if title:
            if title in titles:
                defects.append(
                    SpecDefect(code="duplicate_title", page_id=spec.page_id)
                )
            titles.append(title)
        semantic = []
        for index, element in enumerate(spec.elements):
            if element.type == "image_placeholder":
                defects.append(
                    SpecDefect(
                        code="placeholder",
                        page_id=spec.page_id,
                        element_index=index,
                    )
                )
                continue
            is_background = (
                element.type == "image"
                and element.width >= 12.5
                and element.height >= 7.0
            )
            if (
                not is_background
                and (
                element.x < 0.5
                or element.y < 0.35
                or element.x + element.width > 12.833
                or element.y + element.height > 7.15
                )
            ):
                defects.append(
                    SpecDefect(
                        code="out_of_bounds",
                        page_id=spec.page_id,
                        element_index=index,
                    )
                )
            if (
                element.type in {"text", "bullet"}
                and element.font_size < 18
            ):
                defects.append(
                    SpecDefect(
                        code="font_too_small",
                        page_id=spec.page_id,
                        element_index=index,
                    )
                )
            if element.type == "image":
                if not Path(element.path).is_file():
                    defects.append(
                        SpecDefect(
                            code="missing_image",
                            page_id=spec.page_id,
                            element_index=index,
                        )
                    )
            if (
                element.type == "chart"
                and not spec.source_references
            ):
                defects.append(
                    SpecDefect(code="missing_source", page_id=spec.page_id)
                )
            if not is_background and element.type in {
                "text", "bullet", "image", "chart", "table"
            }:
                semantic.append((index, element))
        for left_index, left in semantic:
            for right_index, right in semantic:
                if right_index <= left_index:
                    continue
                if _overlap_ratio(left, right) > 0.2:
                    defects.append(
                        SpecDefect(
                            code="severe_overlap",
                            page_id=spec.page_id,
                            element_index=right_index,
                        )
                    )
    unique = {
        (item.code, item.page_id, item.element_index): item
        for item in defects
    }
    result = list(unique.values())
    return SpecQualityReport(passed=not result, defects=result)


def repair_specs(
    specs: list[SlideSpec],
    report: SpecQualityReport,
) -> list[SlideSpec]:
    affected = {item.page_id for item in report.defects}
    repaired = []
    for spec in specs:
        if spec.page_id not in affected:
            repaired.append(spec)
            continue
        elements = []
        for element in spec.elements:
            if element.type == "image_placeholder":
                continue
            if element.type == "image" and not Path(element.path).is_file():
                continue
            updates = {}
            if hasattr(element, "font_size") and element.font_size < 18:
                updates["font_size"] = 18
            x = max(0.5, element.x)
            y = max(0.35, element.y)
            width = min(element.width, 12.833 - x)
            height = min(element.height, 7.15 - y)
            updates.update(
                {"x": x, "y": y, "width": width, "height": height}
            )
            elements.append(element.model_copy(update=updates))
        repaired.append(
            spec.model_copy(
                update={
                    "elements": elements,
                    "source_references": list(
                        dict.fromkeys(spec.source_references)
                    ),
                }
            )
        )
    after = inspect_specs(repaired)
    if len(after.defects) >= len(report.defects):
        raise QualityRepairError("repair did not reduce defects")
    return repaired


def _overlap_ratio(left, right) -> float:
    width = max(
        0,
        min(left.x + left.width, right.x + right.width)
        - max(left.x, right.x),
    )
    height = max(
        0,
        min(left.y + left.height, right.y + right.height)
        - max(left.y, right.y),
    )
    intersection = width * height
    denominator = min(
        left.width * left.height,
        right.width * right.height,
    )
    return 0 if denominator == 0 else intersection / denominator
