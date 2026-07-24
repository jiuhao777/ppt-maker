from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.util import Inches, Pt

from pptmaker.m3.models import DesignPlan, SlideSpec


def build_pptx(specs: list[SlideSpec], design: DesignPlan, output_path: Path) -> Path:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    for spec in specs:
        slide = prs.slides.add_slide(blank)
        _set_bg(slide, spec.background_color)

        for el in spec.elements:
            if el.type == "text":
                _add_text(slide, el)
            elif el.type == "bullet":
                _add_bullets(slide, el)
            elif el.type == "rect":
                _add_rect(slide, el)
            elif el.type == "image_placeholder":
                _add_placeholder(slide, el)
            elif el.type == "table":
                _add_table(slide, el)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    return output_path


def _set_bg(slide, color: str):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = _rgb(color)


def _add_text(slide, el):
    box = slide.shapes.add_textbox(Inches(el.x), Inches(el.y), Inches(el.width), Inches(el.height))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = el.text
    p.font.size = Pt(el.font_size)
    p.font.bold = el.bold
    p.font.color.rgb = _rgb(el.color)
    p.font.name = el.font_name


def _add_bullets(slide, el):
    box = slide.shapes.add_textbox(Inches(el.x), Inches(el.y), Inches(el.width), Inches(el.height))
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(el.items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"• {item}"
        p.font.size = Pt(el.font_size)
        p.font.color.rgb = _rgb(el.color)
        p.font.name = el.font_name


def _add_rect(slide, el):
    shape = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(el.x), Inches(el.y),
        Inches(el.width), Inches(el.height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(el.fill_color)
    shape.line.fill.background()


def _add_placeholder(slide, el):
    shape = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(el.x), Inches(el.y),
        Inches(el.width), Inches(el.height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb("#E0E0E0")
    shape.line.color.rgb = _rgb("#CCCCCC")
    tf = shape.text_frame
    tf.word_wrap = True
    tf.paragraphs[0].text = el.description or "[图片区域]"
    tf.paragraphs[0].font.size = Pt(11)
    tf.paragraphs[0].font.color.rgb = _rgb("#999999")


def _add_table(slide, el):
    rows, cols = len(el.rows), len(el.rows[0])
    shape = slide.shapes.add_table(rows, cols, Inches(el.x), Inches(el.y),
                                   Inches(el.width), Inches(el.height))
    for r, row in enumerate(el.rows):
        for c, text in enumerate(row):
            shape.table.cell(r, c).text = text


def _rgb(hex_color: str) -> RGBColor:
    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
