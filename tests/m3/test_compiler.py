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
from pptmaker.m3.compiler import compile_specs
from pptmaker.evaluation.geometry import Box, out_of_bounds, overlap_ratio


def _design() -> DesignPlan:
    from pptmaker.m3.design import PRESETS
    return PRESETS["business"].model_copy(update={"project_id": "p1"})


def _content(pages: list[SlideContent]) -> ContentPlan:
    return ContentPlan(project_id="p1", outline_version=1, slides=pages)


def _page(page_id: str, order: int, title: str, page_type: str = "content", layout: str = "text", **kw) -> SlideContent:
    defaults = dict(body_paragraphs=["body"], bullet_points=[], source_references=[])
    return SlideContent(page_id=page_id, page_type=page_type, layout=layout, title=title, **{**defaults, **kw})


class TestCompileSpecs:
    def test_output_matches_input_page_count(self):
        pages = [_page(f"p{i}", i, f"Page {i}") for i in range(1, 4)]
        specs = compile_specs(_content(pages), _design())
        assert len(specs) == 3

    def test_page_ids_preserved(self):
        pages = [_page("abc", 1, "T"), _page("xyz", 2, "U")]
        specs = compile_specs(_content(pages), _design())
        assert specs[0].page_id == "abc"
        assert specs[1].page_id == "xyz"

    def test_cover_page_type_preserved(self):
        pages = [_page("c", 1, "Cover", page_type="cover")]
        specs = compile_specs(_content(pages), _design())
        assert specs[0].page_type == "cover"

    def test_no_element_out_of_bounds(self):
        pages = [_page(f"p{i}", i, f"Page {i} is a longer title",
                       body_paragraphs=["Paragraph " * 30]) for i in range(1, 5)]
        specs = compile_specs(_content(pages), _design())
        canvas = Box(0, 0, 13.333 * 914400, 7.5 * 914400)  # EMU
        for spec in specs:
            for el in spec.elements:
                box = _element_box(el)
                assert not out_of_bounds(box, canvas), f"{spec.page_id}: {el.type} OOB"

    def test_no_severe_overlap(self):
        pages = [_page("p1", 1, "Title", body_paragraphs=["Body"], bullet_points=["A", "B"])]
        specs = compile_specs(_content(pages), _design())
        for spec in specs:
            boxes = [_element_box(el) for el in spec.elements]
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    assert overlap_ratio(a, b) < 0.2, f"overlap {overlap_ratio(a, b):.2f}"

    def test_cover_has_single_bold_title(self):
        pages = [_page("c", 1, "Cover Title", page_type="cover")]
        specs = compile_specs(_content(pages), _design())
        titles = [e for e in specs[0].elements if e.type == "text" and e.bold]
        assert len(titles) == 1

    def test_content_page_has_title_and_body(self):
        pages = [_page("p1", 1, "Content", body_paragraphs=["Body text"])]
        specs = compile_specs(_content(pages), _design())
        types = {e.type for e in specs[0].elements}
        assert "text" in types

    def test_bullet_points_generate_bullet_element(self):
        pages = [_page("p1", 1, "Bullets", layout="bullets", bullet_points=["A", "B", "C"])]
        specs = compile_specs(_content(pages), _design())
        bullets = [e for e in specs[0].elements if e.type == "bullet"]
        assert len(bullets) == 1
        assert len(bullets[0].items) == 3

    def test_image_suggestion_generates_placeholder(self):
        pages = [_page("p1", 1, "Image", layout="two_column", image_suggestion="chart")]
        specs = compile_specs(_content(pages), _design())
        placeholders = [e for e in specs[0].elements if e.type == "image_placeholder"]
        assert len(placeholders) == 1


def _element_box(el) -> Box:
    # EMU = 914400 per inch
    return Box(
        int(el.x * 914400), int(el.y * 914400),
        int(el.width * 914400), int(el.height * 914400),
    )
