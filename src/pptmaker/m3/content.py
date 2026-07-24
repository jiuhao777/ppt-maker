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
        "展开每页大纲为完整文案。标题≤40字。正文尽量丰富但必须真实。"
        "verified_facts 中的事实优先于模型记忆。无法确认的标注 [待验证]。"
        "引用事实时在 source_references 中填写 source_title。"
        "本版本不生成 key_number 和 key_number_label，请留空。"
        "注意页面信息密度与视觉风格匹配。"
        "为每页选择合适的表达结构，至少产生以下变化："
        "纯文字页、要点列表页、配图建议页、数据陈述页各占一定比例。"
        "image_suggestion 在内容适合配图时才填写（如趋势、对比、架构），"
        "否则留空。bullet_points 适合并列信息时使用。"
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
