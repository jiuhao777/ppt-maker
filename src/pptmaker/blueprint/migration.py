import json

from pptmaker.blueprint.models import DeckBlueprint


def _legacy_page(page: dict) -> dict:
    query = page.pop("asset_search_query", "")
    asset_ids = page.pop("asset_ids", [])
    slots = []
    elements = []
    if query or asset_ids:
        slots.append(
            {
                "slot_id": "hero",
                "role": "hero",
                "subject": query or "页面主视觉",
                "search_query": query or "页面主视觉",
                "purpose": "支撑页面核心结论",
                "required": False,
                "region": {
                    "x": 0.55,
                    "y": 0.18,
                    "width": 0.4,
                    "height": 0.66,
                },
                "fit": "cover",
                "fallback": "simplified_layout",
                "selected_asset_id": asset_ids[0] if asset_ids else None,
            }
        )
        elements.append(
            {
                "element_id": "image-hero",
                "kind": "image",
                "region": slots[0]["region"],
                "z_index": 1,
                "content_ref": "hero",
                "fit": "cover",
            }
        )
    elements.extend(
        [
            {
                "element_id": "title",
                "kind": "title",
                "region": {
                    "x": 0.05,
                    "y": 0.06,
                    "width": 0.9,
                    "height": 0.1,
                },
                "z_index": 2,
                "font_size": 35,
                "content_ref": "conclusion_title",
            },
            {
                "element_id": "body",
                "kind": "body",
                "region": {
                    "x": 0.05,
                    "y": 0.22,
                    "width": 0.44 if slots else 0.9,
                    "height": 0.58,
                },
                "z_index": 2,
                "font_size": 18,
                "content_ref": "primary_message",
            },
        ]
    )
    page["asset_slots"] = slots
    page["layout_elements"] = elements
    return page


def migrate_v1(data: dict) -> dict:
    migrated = dict(data)
    migrated["schema_version"] = 2
    migrated["pages"] = [_legacy_page(dict(page)) for page in data["pages"]]
    return migrated


def load_blueprint(payload: str) -> DeckBlueprint:
    data = json.loads(payload)
    if data.get("schema_version", 1) == 1:
        data = migrate_v1(data)
    return DeckBlueprint.model_validate(data)
