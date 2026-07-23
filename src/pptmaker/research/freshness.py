import re
from dataclasses import dataclass
from typing import Literal

from pptmaker.research.contracts import FreshnessDecision, WebPolicy


Strength = Literal["FORCE", "SUGGEST", "SKIP"]


@dataclass(frozen=True)
class FreshnessRule:
    id: str
    pattern: re.Pattern
    strength: Strength
    reason: str


@dataclass(frozen=True)
class FreshnessSignal:
    rule_id: str
    strength: Strength
    requires_web: bool
    reason: str


def _rule(
    rule_id: str, pattern: str, strength: Strength, reason: str
) -> FreshnessRule:
    return FreshnessRule(rule_id, re.compile(pattern, re.I), strength, reason)


RULES = (
    _rule("R1", r"最新|近期|当前|现状|截至目前", "FORCE", "要求当前信息"),
    _rule("R2", r"趋势|前景|发展|格局|生态", "SUGGEST", "趋势会随时间变化"),
    _rule("R3", r"排名|榜单|第一|领先|代表性", "FORCE", "排名需要近期依据"),
    _rule(
        "R4",
        r"市场规模|份额|销量|用户量|融资",
        "FORCE",
        "市场数据需要近期依据",
    ),
    _rule("R5", r"价格|费用|汇率|利率|估值", "FORCE", "数值会随时间变化"),
    _rule(
        "R6",
        r"(公司|产品|模型|人物).{0,12}(状态|能力|表现)",
        "SUGGEST",
        "对象状态可能变化",
    ),
    _rule("R7", r"政策|法规|标准|监管", "FORCE", "规则可能更新"),
    _rule("R8", r"新闻|事件|发布|更新|版本", "FORCE", "事件具有时效性"),
    _rule("R9", r"竞品|对比|选型|采购建议", "SUGGEST", "比较对象可能变化"),
    _rule(
        "R10",
        r"案例|客户|落地|商业化成果",
        "SUGGEST",
        "案例需要外部证据",
    ),
    _rule(
        "R11",
        r"统计数据|行业数据|公共数据",
        "FORCE",
        "公共数据需要来源",
    ),
    _rule(
        "R12",
        r"(?:19|20[01])\d年|历史时期",
        "SKIP",
        "固定历史时期",
    ),
    _rule(
        "R13",
        r"(?:总结|改写|翻译).{0,12}(?:上传|材料|文档)|"
        r"(?:上传|材料|文档).{0,12}(?:总结|改写|翻译)",
        "SKIP",
        "只处理用户材料",
    ),
    _rule("R14", r"纯创意|头脑风暴|内部流程", "SKIP", "不要求外部事实"),
)


def rule_signals(text: str) -> list[FreshnessSignal]:
    return [
        FreshnessSignal(
            rule_id=rule.id,
            strength=rule.strength,
            requires_web=rule.strength != "SKIP",
            reason=rule.reason,
        )
        for rule in RULES
        if rule.pattern.search(text)
    ]


def _override(requires_web: bool, reason: str) -> FreshnessDecision:
    return FreshnessDecision(
        requires_web=requires_web,
        reason=reason,
        freshness_level="HIGH" if requires_web else "LOW",
    )


def resolve_freshness(
    policy: WebPolicy,
    text: str,
    ai: FreshnessDecision | None,
) -> FreshnessDecision:
    if policy == "ALWAYS":
        return _override(True, "用户要求强制联网")
    if policy == "NEVER":
        return _override(False, "用户禁止联网")

    signals = rule_signals(text)
    forced = [item for item in signals if item.strength == "FORCE"]
    if forced:
        return FreshnessDecision(
            requires_web=True,
            reason="；".join(item.reason for item in forced),
            freshness_level="HIGH",
            verification_topics=[item.reason for item in forced[:5]],
            safe_queries=[text.strip()[:500]] if text.strip() else [],
        )
    if ai is not None:
        return ai
    suggested = [item for item in signals if item.strength == "SUGGEST"]
    if suggested:
        return FreshnessDecision(
            requires_web=True,
            reason="；".join(item.reason for item in suggested),
            freshness_level="MEDIUM",
            verification_topics=[item.reason for item in suggested[:5]],
            safe_queries=[text.strip()[:500]] if text.strip() else [],
        )
    return _override(False, "未发现需要联网核验的时效性信息")
