from pathlib import Path

import pytest

from pptmaker.m0.parser_probe import (
    SENTINEL,
    generate_parser_fixtures,
    measure_parser_matrix,
    parse_markdown,
    parse_pptx,
    parse_with_markitdown,
    run_parser_core_probe,
)


def test_markdown_preserves_heading_table_and_locations():
    parsed = parse_markdown(
        "# 结论\n\n| 指标 | 值 |\n| --- | --- |\n| 质量 | 90 |\n"
    )
    assert parsed.kind == "markdown"
    assert "结论" in parsed.text
    assert parsed.tables == [["指标", "值"], ["质量", "90"]]
    assert parsed.locations == ["line:1", "line:3", "line:5"]


def test_markdown_does_not_parse_pipe_inside_code_fence_as_table():
    parsed = parse_markdown("# 示例\n\n```python\nvalue = left | right\n```\n")
    assert parsed.tables == []
    assert "value = left | right" in parsed.text


def test_pptx_preserves_slide_and_shape_location(tmp_path: Path):
    generate_parser_fixtures(tmp_path)
    parsed = parse_pptx(tmp_path / "sample.pptx")
    assert SENTINEL in parsed.text
    assert parsed.locations == ["slide:1/shape:1"]


def test_pptx_recurses_groups_tables_and_notes(tmp_path: Path):
    generate_parser_fixtures(tmp_path)
    parsed = parse_pptx(tmp_path / "challenge.pptx")
    assert "GROUP_SENTINEL" in parsed.text
    assert "NOTES_SENTINEL" in parsed.text
    assert parsed.tables == [["指标", "值"], ["质量", "90"]]
    assert any("group:" in location for location in parsed.locations)
    assert any("notes:" in location for location in parsed.locations)


def test_parser_core_probe_requires_markdown_pptx_and_location(tmp_path: Path):
    result = run_parser_core_probe(tmp_path)
    assert result.status.value == "pass"
    assert result.metrics["required_checks"] == 3
    assert result.metrics["passed_checks"] == 3
    assert result.metrics["elapsed_seconds"] >= 0


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("sample.docx", SENTINEL),
        ("sample.pdf", SENTINEL),
        ("sample.pptx", SENTINEL),
        ("challenge.pptx", "NOTES_SENTINEL"),
    ],
)
def test_markitdown_extracts_text_sentinel(tmp_path: Path, name: str, expected: str):
    pytest.importorskip("markitdown")
    generate_parser_fixtures(tmp_path)
    parsed = parse_with_markitdown(tmp_path / name)
    assert expected in parsed.text.replace("\\_", "_")
    assert parsed.locations == []


def test_markitdown_image_without_model_is_explicitly_not_ocr(tmp_path: Path):
    pytest.importorskip("markitdown")
    generate_parser_fixtures(tmp_path)
    parsed = parse_with_markitdown(tmp_path / "sample.png")
    assert SENTINEL not in parsed.text


def test_matrix_never_counts_missing_locations_as_full_pass(tmp_path: Path):
    rows = measure_parser_matrix(tmp_path)
    by_name = {row["format"]: row for row in rows}
    assert by_name["markdown-core"]["status"] == "pass"
    assert by_name["pptx-core-challenge"]["status"] == "pass"
    assert by_name["markitdown-docx-sample"]["status"] == "partial"
    assert by_name["markitdown-png-sample"]["status"] == "unsupported"
