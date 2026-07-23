import pytest

from pptmaker.research.contracts import FreshnessDecision
from pptmaker.research.freshness import RULES, resolve_freshness, rule_signals


def decision(requires_web: bool) -> FreshnessDecision:
    return FreshnessDecision(
        requires_web=requires_web,
        reason="AI 判断",
        freshness_level="HIGH" if requires_web else "LOW",
        safe_queries=["公共查询"] if requires_web else [],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("中国大模型现状", True),
        ("2026 年市场份额排名", True),
        ("最新监管政策解读", True),
        ("竞品选型建议", True),
        ("总结我上传的季度汇报", False),
        ("把上传材料翻译成英文", False),
        ("为团队活动头脑风暴", False),
    ],
)
def test_rules_cover_required_examples(text, expected):
    signals = rule_signals(text)

    assert any(item.requires_web for item in signals) is expected


def test_rule_catalog_has_exactly_fourteen_named_rules():
    assert [item.id for item in RULES] == [f"R{i}" for i in range(1, 15)]


def test_user_policy_overrides_ai_and_rules():
    assert not resolve_freshness("NEVER", "最新趋势", decision(True)).requires_web
    assert resolve_freshness("ALWAYS", "翻译材料", decision(False)).requires_web


def test_ai_covers_expression_not_in_rules():
    result = resolve_freshness(
        "AUTO",
        "谁正在引领这个领域",
        decision(True),
    )

    assert result.requires_web
    assert result.reason == "AI 判断"


def test_force_rule_overrides_ai_skip():
    result = resolve_freshness("AUTO", "当前市场份额", decision(False))

    assert result.requires_web


def test_skip_requires_ai_agreement():
    assert not resolve_freshness(
        "AUTO", "总结我上传的季度汇报", decision(False)
    ).requires_web
    assert resolve_freshness(
        "AUTO", "总结我上传的季度汇报", decision(True)
    ).requires_web


def test_invalid_ai_falls_back_to_rules():
    assert resolve_freshness("AUTO", "最新模型", None).requires_web
    assert not resolve_freshness("AUTO", "普通介绍", None).requires_web
