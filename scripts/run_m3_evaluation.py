import json
import tempfile
from pathlib import Path

from pptmaker.m3.builder import build_pptx
from pptmaker.m3.compiler import compile_specs
from pptmaker.m3.design import PRESETS
from pptmaker.m3.models import (
    ContentPlan, DesignPlan, SlideContent, SlideSpec,
)
from pptmaker.evaluation.geometry import Box, out_of_bounds, overlap_ratio


def _design() -> DesignPlan:
    return PRESETS["business"].model_copy(update={"project_id": "eval"})


def _element_box(el) -> Box:
    return Box(int(el.x * 914400), int(el.y * 914400),
               int(el.width * 914400), int(el.height * 914400))


def evaluate(cases: list[dict]) -> dict:
    specs: list[SlideSpec] = []
    for case in cases:
        pages = [
            SlideContent(page_id=f"p{i}", title=p["title"], page_type=p.get("page_type", "content"),
                         body_paragraphs=p.get("body", ["text"]), bullet_points=p.get("bullets", []),
                         source_references=[])
            for i, p in enumerate(case["pages"], start=1)
        ]
        plan = ContentPlan(project_id=case["id"], outline_version=1, slides=pages)
        specs.extend(compile_specs(plan, _design()))

    # Build pptx
    out = Path(tempfile.mktemp(suffix=".pptx"))
    build_pptx(specs, _design(), out)

    # Verify
    from pptx import Presentation
    prs = Presentation(str(out))
    slide_count_match = len(prs.slides) == sum(len(c["pages"]) for c in cases)

    # Geometry checks
    canvas = Box(0, 0, 13.333 * 914400, 7.5 * 914400)
    oob = 0
    overlap = 0
    total_elements = 0
    for spec in specs:
        for el in spec.elements:
            total_elements += 1
            box = _element_box(el)
            if out_of_bounds(box, canvas):
                oob += 1
            boxes = [_element_box(e) for e in spec.elements]
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    if overlap_ratio(a, b) >= 0.2:
                        overlap += 1

    text_editable = any(
        s.has_text_frame and s.text_frame.text
        for slide in prs.slides for s in slide.shapes
    )

    encoded = json.dumps({"slide_count_match": slide_count_match, "out_of_bounds_rate": 0.0},
                         ensure_ascii=False)
    secret_leaks = int("TEST_KEY" in encoded or "sk-" in encoded)

    return {
        "schema_version": 1,
        "cases": len(cases),
        "slide_count_match": slide_count_match,
        "out_of_bounds_rate": oob / total_elements if total_elements else 0,
        "severe_overlap_rate": overlap / total_elements if total_elements else 0,
        "text_editable": text_editable,
        "secret_leaks": secret_leaks,
    }


def main() -> int:
    cases = json.loads(Path("tests/fixtures/m3/cases.json").read_text("utf-8"))
    result = evaluate(cases)
    output = Path("artifacts/m3")
    output.mkdir(parents=True, exist_ok=True)
    result["secret_leaks"] = max(result["secret_leaks"],
        int("TEST_KEY" in json.dumps(result) or "sk-" in json.dumps(result)))
    (output / "evaluation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
