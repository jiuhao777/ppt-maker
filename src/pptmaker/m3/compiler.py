from pptmaker.m3.models import (
    BulletElement,
    ContentPlan,
    DesignPlan,
    ImagePlaceholder,
    RectShape,
    SlideContent,
    SlideSpec,
    TextElement,
)


# Canvas: 16:9 in inches
CANVAS_W = 13.333
CANVAS_H = 7.5
MARGIN_X = 0.7
MARGIN_Y = 0.5
TITLE_H = 1.0
GAP = 0.15


def compile_specs(content: ContentPlan, design: DesignPlan) -> list[SlideSpec]:
    return [_compile_slide(slide, i + 1, design) for i, slide in enumerate(content.slides)]


def _compile_slide(slide: SlideContent, order: int, design: DesignPlan) -> SlideSpec:
    bg = design.palette.background
    font = design.fonts

    if slide.page_type == "cover":
        elements = _cover(slide, font, design)
    elif slide.page_type == "section":
        elements = _section(slide, font, design)
    elif slide.page_type == "ending":
        elements = _ending(slide, font)
    elif slide.page_type == "contents":
        elements = _contents(slide, font, design)
    else:
        elements = _content(slide, font, design)

    return SlideSpec(
        page_id=slide.page_id,
        order=order,
        page_type=slide.page_type,
        background_color=bg,
        elements=elements,
    )


def _cover(slide: SlideContent, font, design: DesignPlan) -> list:
    el = []
    el.append(_text(slide.title, MARGIN_X + 0.5, 2.5, CANVAS_W - 2 * (MARGIN_X + 0.5), 0.8,
                    font.title_size, font.title_zh, bold=True))
    if slide.subtitle:
        el.append(_text(slide.subtitle, MARGIN_X + 0.5, 3.5, CANVAS_W - 2 * (MARGIN_X + 0.5), 0.6,
                        font.subtitle_size, font.body_zh))
    el.append(RectShape(type="rect", x=MARGIN_X, y=6.5, width=CANVAS_W - 2 * MARGIN_X,
                        height=0.03, fill_color=design.palette.accent))
    return el


def _section(slide: SlideContent, font, design) -> list:
    el = []
    el.append(_text(str(slide.order), MARGIN_X, 2.0, 3.0, 1.2,
                    font.title_size + 12, font.title_zh, bold=True))
    el.append(_text(slide.title, MARGIN_X, 3.5, CANVAS_W - 2 * MARGIN_X, 0.8,
                    font.title_size, font.title_zh, bold=True))
    el.append(RectShape(type="rect", x=MARGIN_X, y=4.8, width=CANVAS_W - 2 * MARGIN_X,
                        height=0.03, fill_color=design.palette.accent))
    return el


def _ending(slide: SlideContent, font) -> list:
    el = []
    el.append(_text(slide.title, MARGIN_X, 2.5, CANVAS_W - 2 * MARGIN_X, 0.8,
                    font.title_size, font.title_zh, bold=True))
    if slide.body_paragraphs:
        el.append(_text(slide.body_paragraphs[0], MARGIN_X + 1.0, 3.5,
                        CANVAS_W - 2 * (MARGIN_X + 1.0), 0.6,
                        font.body_size, font.body_zh))
    return el


def _contents(slide: SlideContent, font, design) -> list:
    el = []
    el.append(_text(slide.title, MARGIN_X, MARGIN_Y, CANVAS_W - 2 * MARGIN_X, TITLE_H,
                    font.title_size, font.title_zh, bold=True))
    y = MARGIN_Y + TITLE_H + GAP
    for i, item in enumerate(slide.bullet_points or slide.body_paragraphs or [slide.title]):
        el.append(RectShape(type="rect", x=MARGIN_X, y=y + 0.05, width=0.06, height=0.35,
                            fill_color=design.palette.accent))
        text = f"{i + 1}. {item}" if isinstance(item, str) else str(item)
        el.append(_text(text, MARGIN_X + 0.2, y, CANVAS_W - 2 * MARGIN_X - 0.2, 0.4,
                        font.body_size, font.body_zh))
        y += 0.5
    return el


def _content(slide: SlideContent, font, design) -> list:
    el = []
    # title bar
    el.append(_text(slide.title, MARGIN_X, MARGIN_Y, CANVAS_W - 2 * MARGIN_X, TITLE_H,
                    font.title_size, font.title_zh, bold=True))
    el.append(RectShape(type="rect", x=MARGIN_X, y=MARGIN_Y + TITLE_H, width=CANVAS_W - 2 * MARGIN_X,
                        height=0.02, fill_color=design.palette.accent))

    body_y = MARGIN_Y + TITLE_H + GAP + 0.1
    has_image = bool(slide.image_suggestion)

    if has_image:
        # two-column: text left, placeholder right
        text_w = CANVAS_W - 2 * MARGIN_X - 4.0
        img_x = CANVAS_W - MARGIN_X - 3.5
        el.append(ImagePlaceholder(type="image_placeholder", x=img_x, y=body_y, width=3.5, height=3.0,
                                   description=slide.image_suggestion or ""))
    else:
        text_w = CANVAS_W - 2 * MARGIN_X

    space_h = CANVAS_H - body_y - MARGIN_Y

    # body text
    if slide.body_paragraphs:
        body = "\n\n".join(slide.body_paragraphs)
        rows = min(len(slide.body_paragraphs), 8)
        body_h = min(rows * 0.45, space_h * 0.6)
        el.append(_text(body, MARGIN_X, body_y, text_w, body_h,
                        font.body_size, font.body_zh))

    # bullet points
    if slide.bullet_points:
        bullet_y = body_y + (min(len(slide.body_paragraphs or [""]), 8) * 0.45 if slide.body_paragraphs else 0) + GAP
        el.append(BulletElement(type="bullet", items=slide.bullet_points,
                                x=MARGIN_X + 0.2, y=bullet_y,
                                width=text_w - 0.2,
                                height=space_h - (bullet_y - body_y),
                                font_size=font.body_size, font_name=font.body_zh,
                                color=design.palette.text_primary))
    return el


def _text(text, x, y, w, h, size, name, bold=False) -> TextElement:
    return TextElement(
        type="text", text=text, x=x, y=y, width=w, height=h,
        font_size=size, font_name=name, bold=bold, color="#1A1A1A",
    )
