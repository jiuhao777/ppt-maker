from pptmaker.blueprint.models import (
    BlueprintPage,
    LayoutElementPlan,
    LayoutRegion,
)


def _region(x: float, y: float, width: float, height: float) -> LayoutRegion:
    return LayoutRegion(x=x, y=y, width=width, height=height)


def _image_regions(count: int) -> tuple[LayoutRegion, list[LayoutRegion]]:
    if count == 0:
        return _region(0.05, 0.2, 0.9, 0.62), []
    if count == 1:
        return (
            _region(0.05, 0.2, 0.42, 0.62),
            [_region(0.52, 0.2, 0.43, 0.62)],
        )
    if count == 2:
        return (
            _region(0.05, 0.18, 0.9, 0.16),
            [
                _region(0.05, 0.39, 0.43, 0.43),
                _region(0.52, 0.39, 0.43, 0.43),
            ],
        )
    if count == 3:
        return (
            _region(0.05, 0.2, 0.32, 0.62),
            [
                _region(0.42, 0.2, 0.53, 0.35),
                _region(0.42, 0.59, 0.25, 0.23),
                _region(0.7, 0.59, 0.25, 0.23),
            ],
        )
    return (
        _region(0.05, 0.2, 0.26, 0.62),
        [
            _region(0.36, 0.2, 0.28, 0.29),
            _region(0.67, 0.2, 0.28, 0.29),
            _region(0.36, 0.53, 0.28, 0.29),
            _region(0.67, 0.53, 0.28, 0.29),
        ],
    )


def plan_page_layout(page: BlueprintPage) -> BlueprintPage:
    slots = list(page.asset_slots)
    body_region, image_regions = _image_regions(len(slots))
    if (
        len(slots) == 1
        and slots[0].role == "background"
        and page.page_type in {"cover", "section", "quote", "ending"}
    ):
        image_regions = [_region(0, 0, 1, 1)]
        body_region = _region(0.08, 0.25, 0.64, 0.45)

    updated_slots = [
        slot.model_copy(update={"region": image_regions[index]})
        for index, slot in enumerate(slots)
    ]
    elements = [
        LayoutElementPlan(
            element_id="title",
            kind="title",
            region=_region(0.05, 0.05, 0.9, 0.1),
            z_index=10,
            font_size=35,
            content_ref="conclusion_title",
        ),
        LayoutElementPlan(
            element_id="body",
            kind="body",
            region=body_region,
            z_index=10,
            font_size=18,
            content_ref="primary_message",
        ),
    ]
    elements.extend(
        LayoutElementPlan(
            element_id=f"image-{slot.slot_id}",
            kind="image",
            region=slot.region,
            z_index=slot.z_index,
            content_ref=slot.slot_id,
            fit=slot.fit,
        )
        for slot in updated_slots
    )
    elements.extend(
        [
            LayoutElementPlan(
                element_id="footer",
                kind="footer",
                region=_region(0.05, 0.91, 0.82, 0.04),
                z_index=10,
                font_size=10,
                color_token="text_secondary",
                content_ref="footer",
            ),
            LayoutElementPlan(
                element_id="page-number",
                kind="page_number",
                region=_region(0.9, 0.91, 0.05, 0.04),
                z_index=10,
                font_size=10,
                alignment="right",
                color_token="text_secondary",
                content_ref="order",
            ),
        ]
    )
    return BlueprintPage.model_validate(
        page.model_dump()
        | {
            "asset_slots": [
                item.model_dump() for item in updated_slots
            ],
            "layout_elements": [item.model_dump() for item in elements],
        }
    )


def construction_summary(page: BlueprintPage) -> str:
    images = "；".join(
        f"{slot.subject}（{slot.role}，"
        f"x={slot.region.x:.0%}, y={slot.region.y:.0%}, "
        f"宽={slot.region.width:.0%}, 高={slot.region.height:.0%}）"
        for slot in page.asset_slots
    ) or "无额外配图"
    return "\n".join(
        [
            f"▌核心结论：{page.conclusion_title}",
            f"▌布局：{page.visual.layout}；{page.visual.ratio}",
            f"▌一级信息：{page.primary_message}",
            "▌二级信息：" + "；".join(page.supporting_points),
            f"▌视觉要求：{images}",
            f"▌演讲备注：{page.speaker_notes}",
            f"▌逻辑衔接：{page.previous_bridge} → {page.next_bridge}",
        ]
    )
