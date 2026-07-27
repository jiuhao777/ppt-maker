from pptmaker.assets.models import AssetRecord
from pptmaker.blueprint.models import BlueprintPage, DeckBible
from pptmaker.m3.models import (
    BulletElement,
    ChartElement,
    DesignPlan,
    ImageElement,
    LineElement,
    RectShape,
    SlideSpec,
    TextElement,
)
from pptmaker.research.contracts import FactRecord


CANVAS_W = 13.333
CANVAS_H = 7.5
LEFT = 0.7
RIGHT = 12.633
TOP = 0.45
BOTTOM = 7.15


def _text(
    value: str,
    x: float,
    y: float,
    width: float,
    height: float,
    size: int,
    design: DesignPlan,
    *,
    bold: bool = False,
    color: str | None = None,
) -> TextElement:
    return TextElement(
        text=value,
        x=x,
        y=y,
        width=width,
        height=height,
        font_size=size,
        font_name=design.fonts.title_zh if bold else design.fonts.body_zh,
        bold=bold,
        color=color or design.palette.text_primary,
    )


def _title(page: BlueprintPage, design: DesignPlan) -> TextElement:
    return _text(
        page.conclusion_title,
        LEFT,
        TOP,
        RIGHT - LEFT,
        0.75,
        max(35, design.fonts.title_size),
        design,
        bold=True,
    )


def _bullets(
    page: BlueprintPage,
    design: DesignPlan,
    x=0.8,
    y=1.65,
    width=11.7,
    height=4.8,
) -> BulletElement | None:
    if not page.supporting_points:
        return None
    return BulletElement(
        items=page.supporting_points[:3],
        x=x,
        y=y,
        width=width,
        height=height,
        font_size=max(18, design.fonts.body_size),
        font_name=design.fonts.body_zh,
        color=design.palette.text_primary,
    )


def _standard(page, design):
    elements = [_title(page, design)]
    bullet = _bullets(page, design)
    if bullet:
        elements.append(bullet)
    elif page.primary_message:
        elements.append(
            _text(
                page.primary_message,
                0.9,
                1.8,
                11.4,
                3.8,
                max(20, design.fonts.body_size),
                design,
            )
        )
    return elements


def _cover(page, design):
    return [
        _text(
            page.conclusion_title,
            1.1,
            2.25,
            11.1,
            1.2,
            max(50, design.fonts.title_size),
            design,
            bold=True,
        ),
        _text(
            page.primary_message,
            1.1,
            3.65,
            10.5,
            0.8,
            max(24, design.fonts.subtitle_size),
            design,
            color=design.palette.text_secondary,
        ),
        LineElement(
            x=1.1,
            y=5.0,
            width=3.0,
            height=0,
            color=design.palette.accent,
            line_width=4,
        ),
    ]


def _contents(page, design):
    elements = [_title(page, design)]
    bullet = _bullets(page, design, x=1.2, y=1.65, width=10.8, height=4.9)
    if bullet:
        elements.append(bullet)
    return elements


def _section(page, design):
    return [
        _text(
            f"{page.order:02d}",
            0.8,
            1.55,
            2.2,
            1.2,
            48,
            design,
            bold=True,
            color=design.palette.accent,
        ),
        _text(
            page.conclusion_title,
            3.0,
            2.0,
            9.2,
            1.0,
            max(40, design.fonts.title_size),
            design,
            bold=True,
        ),
        _text(
            page.primary_message,
            3.0,
            3.25,
            8.8,
            1.2,
            22,
            design,
            color=design.palette.text_secondary,
        ),
    ]


def _center_statement(page, design):
    return [
        _text(
            page.conclusion_title,
            1.15,
            2.0,
            11.0,
            1.35,
            max(42, design.fonts.title_size),
            design,
            bold=True,
        ),
        _text(
            page.primary_message,
            1.5,
            3.65,
            10.3,
            1.1,
            24,
            design,
            color=design.palette.text_secondary,
        ),
    ]


def _image_text(page, design, assets):
    elements = [_title(page, design)]
    bullet = _bullets(page, design, width=5.3)
    if bullet:
        elements.append(bullet)
    if assets:
        elements.append(
            ImageElement(
                path=assets[0].local_path,
                x=6.55,
                y=1.45,
                width=6.0,
                height=5.25,
            )
        )
    return elements


def _cards(page, design):
    elements = [_title(page, design)]
    points = page.supporting_points or [page.primary_message]
    for index, point in enumerate(points[:3]):
        x = 0.7 + index * 4.05
        elements.extend(
            [
                RectShape(
                    x=x,
                    y=1.7,
                    width=3.65,
                    height=4.65,
                    fill_color=design.palette.secondary,
                ),
                _text(
                    point,
                    x + 0.3,
                    2.15,
                    3.05,
                    2.8,
                    22,
                    design,
                    bold=True,
                ),
            ]
        )
    return elements


def _comparison(page, design):
    elements = [_title(page, design)]
    points = page.supporting_points or [page.primary_message]
    for index in range(2):
        x = 0.75 + index * 6.05
        value = points[index] if index < len(points) else "—"
        elements.extend(
            [
                RectShape(
                    x=x,
                    y=1.65,
                    width=5.55,
                    height=4.8,
                    fill_color=(
                        design.palette.secondary
                        if index == 0
                        else design.palette.background
                    ),
                ),
                _text(
                    value,
                    x + 0.4,
                    2.1,
                    4.75,
                    3.2,
                    24,
                    design,
                    bold=True,
                ),
            ]
        )
    return elements


def _timeline(page, design):
    elements = [
        _title(page, design),
        LineElement(
            x=1.0,
            y=3.45,
            width=11.2,
            height=0,
            color=design.palette.accent,
            line_width=3,
        ),
    ]
    points = page.supporting_points or [page.primary_message]
    for index, point in enumerate(points[:3]):
        x = 1.0 + index * 4.1
        elements.append(
            _text(point, x, 3.75, 3.4, 1.4, 20, design, bold=True)
        )
    return elements


def _process(page, design):
    elements = [_title(page, design)]
    points = page.supporting_points or [page.primary_message]
    for index, point in enumerate(points[:3]):
        x = 0.75 + index * 4.05
        elements.extend(
            [
                RectShape(
                    x=x,
                    y=2.0,
                    width=3.4,
                    height=2.8,
                    fill_color=design.palette.secondary,
                ),
                _text(
                    f"{index + 1}. {point}",
                    x + 0.3,
                    2.45,
                    2.8,
                    1.8,
                    20,
                    design,
                    bold=True,
                ),
            ]
        )
    return elements


def _architecture(page, design):
    elements = [_title(page, design)]
    points = page.supporting_points or [page.primary_message]
    for index, point in enumerate(points[:3]):
        y = 1.6 + index * 1.65
        elements.extend(
            [
                RectShape(
                    x=1.2,
                    y=y,
                    width=10.8,
                    height=1.25,
                    fill_color=design.palette.secondary,
                ),
                _text(
                    point,
                    1.65,
                    y + 0.25,
                    9.9,
                    0.65,
                    20,
                    design,
                    bold=True,
                ),
            ]
        )
    return elements


def _chart(page, design):
    data = page.visual.chart_data
    elements = [_title(page, design)]
    bullet = _bullets(page, design, width=3.7)
    if bullet:
        elements.append(bullet)
    if data:
        elements.append(
            ChartElement(
                chart_type=(page.visual.chart_type or "column"),
                categories=data.categories,
                series={
                    item.name: [float(value) for value in item.values]
                    for item in data.series
                },
                x=4.65,
                y=1.5,
                width=7.9,
                height=5.1,
            )
        )
    return elements


def _case(page, design):
    elements = [_title(page, design)]
    elements.append(
        _text(
            page.primary_message,
            0.85,
            1.55,
            4.1,
            4.9,
            24,
            design,
            bold=True,
        )
    )
    bullet = _bullets(page, design, x=5.25, width=7.0)
    if bullet:
        elements.append(bullet)
    return elements


def _interaction(page, design):
    return [
        _title(page, design),
        _text(
            page.primary_message,
            1.2,
            2.0,
            10.8,
            1.3,
            30,
            design,
            bold=True,
        ),
        RectShape(
            x=2.0,
            y=4.0,
            width=9.3,
            height=1.2,
            fill_color=design.palette.secondary,
        ),
    ]


def layout_page(
    page: BlueprintPage,
    bible: DeckBible,
    design: DesignPlan,
    facts: list[FactRecord],
    assets: list[AssetRecord],
) -> SlideSpec:
    effective_type = page.page_type
    if page.visual.kind in {"photo", "illustration"} and effective_type == "text":
        effective_type = "image_text"
    elif page.visual.kind == "chart" and effective_type == "text":
        effective_type = "data_chart"
    handlers = {
        "cover": lambda: _cover(page, design),
        "contents": lambda: _contents(page, design),
        "section": lambda: _section(page, design),
        "conclusion": lambda: _center_statement(page, design),
        "text": lambda: _standard(page, design),
        "image_text": lambda: _image_text(page, design, assets),
        "cards": lambda: _cards(page, design),
        "comparison": lambda: _comparison(page, design),
        "timeline": lambda: _timeline(page, design),
        "process": lambda: _process(page, design),
        "architecture": lambda: _architecture(page, design),
        "data_chart": lambda: _chart(page, design),
        "case": lambda: _case(page, design),
        "quote": lambda: _center_statement(page, design),
        "interaction": lambda: _interaction(page, design),
        "qa": lambda: _interaction(page, design),
        "ending": lambda: _center_statement(page, design),
    }
    elements = handlers[effective_type]()
    sources = [
        f"{item.source_title} · {item.source_url}" for item in facts
    ]
    sources.extend(
        f"{item.attribution or item.creator or '作者未知'} · "
        f"{item.landing_url}"
        for item in assets
    )
    return SlideSpec(
        page_id=page.page_id,
        order=page.order,
        page_type=page.page_type,
        background_color=design.palette.background,
        elements=elements,
        speaker_notes=page.speaker_notes,
        source_references=sources,
        transition="fade" if bible.animation_level == "simple" else "none",
    )
