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
        elements = _content(slide, font, design) if slide.layout == "text" else \
                   _bullets_layout(slide, font, design) if slide.layout == "bullets" else \
                   _two_column(slide, font, design) if slide.layout == "two_column" else \
                   _big_number(slide, font, design) if slide.layout == "big_number" else \
                   _comparison(slide, font, design) if slide.layout == "comparison" else \
                   _table_layout(slide, font, design) if slide.layout == "table" else \
                   _quote_layout(slide, font, design)

    return SlideSpec(page_id=slide.page_id, order=order, page_type=slide.page_type,
                     background_color=bg, elements=elements)


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
    """text layout — 正文段落"""
    return _title_bar(slide, font, design) + _body_text(slide, font, body_y=TITLE_H + MARGIN_Y + GAP + 0.1)


def _bullets_layout(slide: SlideContent, font, design) -> list:
    """要点列表"""
    el = _title_bar(slide, font, design)
    items = slide.bullet_points if slide.bullet_points else slide.body_paragraphs
    if items:
        el.append(BulletElement(type="bullet", items=items, x=MARGIN_X + 0.3, y=TITLE_H + MARGIN_Y + GAP + 0.1,
                                width=CANVAS_W - 2 * MARGIN_X - 0.3, height=CANVAS_H - TITLE_H - MARGIN_Y * 2 - GAP,
                                font_size=font.body_size + 2, font_name=font.body_zh, color=design.palette.text_primary))
    return el


def _two_column(slide: SlideContent, font, design) -> list:
    """双栏 — 左文字、右要点/图片"""
    el = _title_bar(slide, font, design)
    y = TITLE_H + MARGIN_Y + GAP + 0.1
    mid = MARGIN_X + (CANVAS_W - 2 * MARGIN_X) / 2 + 0.3
    left_w = mid - MARGIN_X - 0.2
    right_w = CANVAS_W - MARGIN_X - mid - 0.2
    space_h = CANVAS_H - y - MARGIN_Y

    if slide.body_paragraphs:
        body = "\n\n".join(slide.body_paragraphs)
        el.append(_text(body, MARGIN_X, y, left_w, space_h, font.body_size, font.body_zh))
    if slide.bullet_points:
        el.append(BulletElement(type="bullet", items=slide.bullet_points, x=mid, y=y,
                                width=right_w, height=space_h, font_size=font.body_size,
                                font_name=font.body_zh, color=design.palette.text_primary))
    if slide.image_suggestion:
        el.append(ImagePlaceholder(type="image_placeholder", x=mid, y=y, width=right_w, height=min(space_h, 3.5),
                                   description=slide.image_suggestion))
    return el


def _big_number(slide: SlideContent, font, design) -> list:
    """大字数据突出"""
    el = _title_bar(slide, font, design)
    y = TITLE_H + MARGIN_Y + GAP + 0.5
    el.append(_text(slide.body_paragraphs[0] if slide.body_paragraphs else slide.title,
                    MARGIN_X + 1.0, y, CANVAS_W - 2 * (MARGIN_X + 1.0), 2.5,
                    font.title_size + 8, font.title_zh, bold=True))
    if len(slide.body_paragraphs) > 1:
        el.append(_text(slide.body_paragraphs[1], MARGIN_X + 1.0, y + 2.8, CANVAS_W - 2 * (MARGIN_X + 1.0), 0.6,
                        font.subtitle_size, font.body_zh))
    return el


def _comparison(slide: SlideContent, font, design) -> list:
    """对比布局 — 左右对比"""
    el = _title_bar(slide, font, design)
    y = TITLE_H + MARGIN_Y + GAP + 0.2
    mid = MARGIN_X + (CANVAS_W - 2 * MARGIN_X) / 2
    w = (CANVAS_W - 2 * MARGIN_X) / 2 - 0.5
    h = CANVAS_H - y - MARGIN_Y
    items = slide.bullet_points if slide.bullet_points else ["项目A", "项目B"]

    for i, (side, label) in enumerate([(MARGIN_X + 0.2, items[0] if len(items) > 0 else "A"),
                                        (mid + 0.3, items[1] if len(items) > 1 else "B")]):
        bg_rect = RectShape(type="rect", x=side - 0.2, y=y, width=w + 0.4, height=h,
                            fill_color=design.palette.secondary if i == 0 else design.palette.background)
        el.append(bg_rect)
        el.append(_text(label, side + 0.3, y + GAP, w - 0.6, h - GAP * 2,
                        font.body_size + 2, font.body_zh, bold=True))
    return el


def _table_layout(slide: SlideContent, font, design) -> list:
    """表格"""
    el = _title_bar(slide, font, design)
    rows = slide.table_rows or [["列1", "列2"], ["", ""]]
    y = TITLE_H + MARGIN_Y + GAP + 0.1
    el.append(TableBlock(type="table", rows=rows, x=MARGIN_X, y=y,
                         width=CANVAS_W - 2 * MARGIN_X,
                         height=min(len(rows) * 0.45 + 0.3, CANVAS_H - y - MARGIN_Y),
                         font_size=font.body_size))
    return el


def _quote_layout(slide: SlideContent, font, design) -> list:
    """引用"""
    el = []
    quote = slide.body_paragraphs[0] if slide.body_paragraphs else slide.title
    el.append(RectShape(type="rect", x=MARGIN_X + 1.5, y=2.0, width=0.05, height=2.5,
                        fill_color=design.palette.accent))
    el.append(_text(f"「{quote}」", MARGIN_X + 2.0, 2.2, CANVAS_W - 2 * MARGIN_X - 2.5, 1.5,
                    font.title_size - 2, font.title_zh))
    if len(slide.body_paragraphs) > 1:
        el.append(_text(f"—— {slide.body_paragraphs[1]}", MARGIN_X + 2.0, 4.0,
                        CANVAS_W - 2 * MARGIN_X - 2.5, 0.5, font.subtitle_size, font.body_zh))
    return el


def _title_bar(slide: SlideContent, font, design) -> list:
    el = []
    el.append(_text(slide.title, MARGIN_X, MARGIN_Y, CANVAS_W - 2 * MARGIN_X, TITLE_H,
                    font.title_size, font.title_zh, bold=True))
    el.append(RectShape(type="rect", x=MARGIN_X, y=MARGIN_Y + TITLE_H, width=CANVAS_W - 2 * MARGIN_X,
                        height=0.02, fill_color=design.palette.accent))
    return el


def _body_text(slide: SlideContent, font, body_y: float) -> list:
    if not slide.body_paragraphs:
        return []
    body = "\n\n".join(slide.body_paragraphs)
    h = CANVAS_H - body_y - MARGIN_Y
    return [_text(body, MARGIN_X, body_y, CANVAS_W - 2 * MARGIN_X, h, font.body_size, font.body_zh)]


def _text(text, x, y, w, h, size, name, bold=False) -> TextElement:
    return TextElement(
        type="text", text=text, x=x, y=y, width=w, height=h,
        font_size=size, font_name=name, bold=bold, color="#1A1A1A",
    )
