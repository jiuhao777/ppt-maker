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
        "为每页大纲生成完整文案。标题≤40字。"
        "每页的 layout、image_suggestion、icon_suggestion 已在大纲中确定，"
        "请沿用，不需要重新选择或修改。"
        "verified_facts 中的事实优先于模型记忆。无法确认的标注 [待验证]。"
        "引用事实时在 source_references 中填写 source_title。"
        "本版本不生成 key_number 和 key_number_label，请留空。"
        "table 型页面必须填写 table_rows，第一行为表头。"
        "body_paragraphs 根据需要分行，每段≤200字。"
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
