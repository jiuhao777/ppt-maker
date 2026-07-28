import json

from pptmaker.blueprint.migration import load_blueprint
from tests.blueprint.factories import blueprint


def test_schema_one_single_asset_becomes_hero_slot():
    payload = blueprint(page_count=1).model_dump(mode="json")
    payload["schema_version"] = 1
    payload["pages"][0]["asset_search_query"] = "DeepSeek logo"
    payload["pages"][0]["asset_ids"] = ["asset-1"]
    payload["pages"][0].pop("asset_slots", None)
    payload["pages"][0].pop("layout_elements", None)

    migrated = load_blueprint(json.dumps(payload))

    slot = migrated.pages[0].asset_slots[0]
    assert migrated.schema_version == 2
    assert slot.role == "hero"
    assert slot.search_query == "DeepSeek logo"
    assert slot.selected_asset_id == "asset-1"


def test_schema_one_without_image_migrates_to_text_layout():
    payload = blueprint(page_count=1).model_dump(mode="json")
    payload["schema_version"] = 1
    payload["pages"][0].pop("asset_slots", None)
    payload["pages"][0].pop("layout_elements", None)

    migrated = load_blueprint(json.dumps(payload))

    assert migrated.pages[0].asset_slots == []
    assert {item.kind for item in migrated.pages[0].layout_elements} == {
        "title",
        "body",
    }
