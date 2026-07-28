import pytest

from pptmaker.blueprint.layout_planner import (
    construction_summary,
    plan_page_layout,
)
from pptmaker.blueprint.models import AssetSlot, LayoutRegion
from tests.blueprint.factories import page


def _slot(slot_id: str, *, role: str = "photo") -> AssetSlot:
    return AssetSlot(
        slot_id=slot_id,
        role=role,
        subject=f"图片 {slot_id}",
        search_query=f"图片 {slot_id}",
        purpose="支撑结论",
        region=LayoutRegion(x=0.1, y=0.2, width=0.3, height=0.3),
    )


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
def test_layout_planner_represents_every_image_slot(count):
    source = page("p1", 1).model_copy(
        update={"asset_slots": [_slot(f"image-{n}") for n in range(count)]}
    )

    planned = plan_page_layout(source)

    refs = {
        item.content_ref
        for item in planned.layout_elements
        if item.kind == "image"
    }
    assert refs == {item.slot_id for item in planned.asset_slots}


@pytest.mark.parametrize("page_type", ["cover", "section", "quote", "ending"])
def test_special_pages_support_a_selected_image(page_type):
    source = page("p1", 1).model_copy(
        update={"page_type": page_type, "asset_slots": [_slot("hero")]}
    )
    planned = plan_page_layout(source)
    assert any(item.kind == "image" for item in planned.layout_elements)


def test_background_slot_covers_special_page():
    source = page("p1", 1).model_copy(
        update={
            "page_type": "ending",
            "asset_slots": [_slot("background", role="background")],
        }
    )
    planned = plan_page_layout(source)
    assert planned.asset_slots[0].region == LayoutRegion(
        x=0, y=0, width=1, height=1
    )


def test_construction_summary_contains_required_sections():
    planned = plan_page_layout(page("p1", 1))
    summary = construction_summary(planned)
    assert "核心结论" in summary
    assert "布局" in summary
    assert "演讲备注" in summary
    assert "逻辑衔接" in summary
