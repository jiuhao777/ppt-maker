import pytest

from pptmaker.m3.models import ImageElement, SlideSpec, TextElement
from pptmaker.m3.quality import (
    QualityRepairError,
    inspect_specs,
    repair_specs,
)


def text(**updates):
    values = {
        "text": "Title",
        "x": 0.7,
        "y": 0.5,
        "width": 5,
        "height": 0.8,
        "font_size": 35,
        "font_name": "Arial",
        "bold": True,
        "color": "#111111",
    }
    values.update(updates)
    return TextElement(**values)


def spec(page_id="p1", order=1, elements=None, sources=None):
    return SlideSpec(
        page_id=page_id,
        order=order,
        page_type="text",
        background_color="#FFFFFF",
        elements=elements or [text()],
        source_references=sources or [],
    )


def test_inspector_detects_bounds_font_overlap_and_duplicate_title():
    first = spec(
        elements=[
            text(x=0.1, font_size=12),
            text(text="Body", x=0.2, y=0.5, bold=False),
        ]
    )
    second = spec(page_id="p2", order=2)

    codes = {
        item.code for item in inspect_specs([first, second]).defects
    }

    assert {"out_of_bounds", "font_too_small", "severe_overlap"} <= codes
    assert "duplicate_title" in codes


def test_repair_reduces_defects_and_preserves_unaffected_page():
    broken = spec(elements=[text(x=0.1, font_size=12)])
    unaffected = spec(
        page_id="p2", order=2, elements=[text(text="Other")]
    )
    original = unaffected.model_dump_json()
    report = inspect_specs([broken, unaffected])

    repaired = repair_specs([broken, unaffected], report)

    assert len(inspect_specs(repaired).defects) < len(report.defects)
    assert repaired[1].model_dump_json() == original
    assert repaired[0].elements[0].x == 0.5
    assert repaired[0].elements[0].font_size == 18


def test_missing_image_is_removed_but_missing_source_is_not_invented(tmp_path):
    image = ImageElement(
        path=str(tmp_path / "missing.png"),
        x=7,
        y=1.5,
        width=5,
        height=4,
    )
    item = spec(elements=[text(), image], sources=["Asset source"])
    report = inspect_specs([item])

    repaired = repair_specs([item], report)

    assert not any(el.type == "image" for el in repaired[0].elements)


def test_unrepairable_overlap_is_rejected():
    item = spec(
        elements=[
            text(),
            text(text="Body", x=0.7, y=0.5, bold=False),
        ]
    )
    report = inspect_specs([item])

    with pytest.raises(QualityRepairError):
        repair_specs([item], report)
