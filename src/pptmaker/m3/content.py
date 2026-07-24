import json

from pptmaker.m2.models import (
    DeckOutline,
    MaterialChunk,
    RequirementBrief,
)
from pptmaker.m3.models import ContentPlan, DesignPlan
from pptmaker.providers.structured import StructuredModel, StructuredOutputError
from pptmaker.research.contracts import FactRecord


def plan_content(
    brief: RequirementBrief,
    outline: DeckOutline,
    design: DesignPlan,
    chunks: list[MaterialChunk],
    facts: list[FactRecord],
    model: StructuredModel,
    api_key: str,
) -> ContentPlan:
    active_facts = [f for f in facts if not f.excluded]
    evidence = json.dumps({
        "requirements": brief.model_dump(mode="json"),
        "outline": outline.model_dump(mode="json"),
        "design": {"style_notes": design.style_notes, "palette": design.palette.model_dump()},
        "materials": [{"source": c.source_name, "text": c.text} for c in chunks],
        "verified_facts": [{"statement": f.statement, "source_title": f.source_title}
                           for f in active_facts],
    }, ensure_ascii=False)[:100_000]

    system = (
        "为每页大纲生成完整文案和排版方案。标题≤40字。"
        "verified_facts 中的事实优先于模型记忆。无法确认的标注 [待验证]。"
        "引用事实时在 source_references 中填写 source_title。"
        "本版本不生成 key_number 和 key_number_label，请留空。"
        ""
        "每页必须指定 layout 字段，从以下类型中选择最合适的："
        "  text — 纯文字段落，适合叙述性内容"
        "  bullets — 要点列表，适合并列信息、清单"
        "  two_column — 双栏布局，左文字右要点或左要点右文字"
        "  big_number — 数据突出，body 简短，key_number 暂留空"
        "  comparison — 对比布局，bullet_points 为左右对比项"
        "  table — 表格数据，同时填写 table_rows（每行一个list）"
        "  quote — 引用/金句，body_paragraphs[0] 为引用内容"
        ""
        "image_suggestion 只在有明确配图需求时才填"
        "（如趋势图、对比图、架构图），否则留空。"
        "table 型页面必须填写 table_rows，第一行为表头。"
        "各类型至少出现一次，避免所有页用同一种 layout。"
    )

    try:
        return _generate(model, system, evidence, api_key)
    except StructuredOutputError:
        try:
            return _generate(model, system + " 修正上次的结构错误。", evidence, api_key)
        except StructuredOutputError:
            raise


def _generate(model, system, evidence, api_key):
    return model.generate(ContentPlan, system, evidence, api_key)
