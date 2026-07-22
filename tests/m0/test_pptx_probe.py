from pathlib import Path
from zipfile import ZipFile

from pptmaker.m0.pptx_probe import build_baseline_deck


def test_baseline_deck_contains_editable_content(tmp_path: Path):
    output = tmp_path / "baseline.pptx"
    result = build_baseline_deck(output)

    assert result.status.value == "pass"
    assert result.metrics == {
        "slides": 2,
        "text_boxes": 2,
        "shapes": 1,
        "tables": 1,
        "images": 1,
        "charts": 1,
    }
    with ZipFile(output) as package:
        names = set(package.namelist())
        slide_text = package.read("ppt/slides/slide1.xml").decode("utf-8")

    assert "ppt/slides/slide1.xml" in names
    assert "ppt/slides/slide2.xml" in names
    assert any(name.startswith("ppt/charts/chart") for name in names)
    assert any(name.startswith("ppt/media/image") for name in names)
    assert "PPT Maker 技术验证" in slide_text
