import json
from pathlib import Path

from scripts.run_m3_evaluation import evaluate


def test_evaluation_covers_every_supported_contract():
    cases = json.loads(
        Path("tests/fixtures/m3/cases.json").read_text(encoding="utf-8")
    )

    report = evaluate(cases)

    assert report["crashes"] == []
    assert set(report["layouts_exercised"]) == {
        "text",
        "bullets",
        "two_column",
        "big_number",
        "comparison",
        "table",
        "quote",
    }
    assert {
        "cover",
        "contents",
        "section",
        "content",
        "ending",
    } <= set(report["page_types_exercised"])
