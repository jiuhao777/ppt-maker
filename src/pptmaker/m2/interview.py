import json

from pptmaker.m2.models import (
    ConversationTurn,
    GapCandidate,
    InterviewQuestion,
    MaterialChunk,
    RequirementBrief,
    RequirementField,
)
from pptmaker.providers.structured import StructuredModel


DEFAULT_PRIORITY = {
    "purpose": 50,
    "scenario": 40,
    "target_slides": 35,
    "audience": 30,
    "priorities": 20,
    "style": 10,
}
QUESTIONS = {
    "purpose": (
        "这份演示文稿要解决什么问题或达成什么目标？",
        "为了确定整份大纲的叙事方向，需要先明确演示目标。",
    ),
    "scenario": (
        "这份演示文稿会在什么场景下使用？",
        "为了安排章节节奏和信息密度，需要了解实际演示场景。",
    ),
    "target_slides": (
        "你希望大约制作多少页？",
        "为了控制内容范围和章节分配，需要确定目标页数。",
    ),
    "audience": (
        "主要受众是谁？",
        "为了选择信息深度和表达方式，需要了解受众。",
    ),
    "priorities": (
        "最希望重点呈现哪些内容？",
        "为了确定页面资源分配，需要明确核心重点。",
    ),
    "style": (
        "希望整体采用什么表达或视觉风格？",
        "为了让大纲结构与最终呈现方向一致，需要确认风格。",
    ),
}


def _missing(value: RequirementField) -> bool:
    return value.value is None or value.value == ""


def _needs_confirmation(value: RequirementField) -> bool:
    return _missing(value) or (value.confidence < 0.6 and not value.assumed)


def rank_gaps(brief: RequirementBrief) -> list[GapCandidate]:
    gaps = []
    for field_name, priority in DEFAULT_PRIORITY.items():
        value = getattr(brief, field_name)
        if field_name == "target_slides" and not _missing(brief.duration_minutes):
            continue
        if _needs_confirmation(value):
            gaps.append(
                GapCandidate(
                    field=field_name,
                    score=100 + priority + (1 - value.confidence) * 20,
                    blocking=True,
                )
            )
    return sorted(gaps, key=lambda item: item.score, reverse=True)


def plan_next_question(brief: RequirementBrief) -> InterviewQuestion | None:
    gaps = rank_gaps(brief)
    if not gaps:
        return None
    field_name = gaps[0].field
    text, reason = QUESTIONS[field_name]
    return InterviewQuestion(field=field_name, text=text, reason=reason)


def accept_unknown(
    brief: RequirementBrief,
    field_name: str,
    assumption: str,
) -> RequirementBrief:
    if field_name not in DEFAULT_PRIORITY:
        raise ValueError("field cannot be assumed")
    return brief.model_copy(
        update={
            field_name: RequirementField(
                value=assumption,
                confidence=0.25,
                source="assumption",
                assumed=True,
            )
        }
    )


def extract_requirements(
    project_id: str,
    chunks: list[MaterialChunk],
    turns: list[ConversationTurn],
    model: StructuredModel,
    api_key: str,
    *,
    current: RequirementBrief | None = None,
) -> RequirementBrief:
    evidence = {
        "materials": [
            {
                "source": chunk.source_name,
                "location": chunk.location,
                "text": chunk.text,
            }
            for chunk in chunks
        ],
        "conversation": [
            {"role": turn.role, "field": turn.field, "content": turn.content}
            for turn in turns
        ],
    }
    extracted = model.generate(
        RequirementBrief,
        (
            "提取演示文稿需求。只能使用输入中的证据；未知字段保持为空。"
            "每个已提取字段必须填写 confidence 和 source。"
        ),
        json.dumps(evidence, ensure_ascii=False)[:100_000],
        api_key,
    )
    base = current or RequirementBrief(project_id=project_id)
    updates = {}
    for field_name in RequirementBrief.model_fields:
        if field_name in {"schema_version", "project_id"}:
            continue
        existing = getattr(base, field_name)
        candidate = getattr(extracted, field_name)
        if existing.source == "user":
            continue
        if not _missing(candidate) and candidate.confidence > existing.confidence:
            updates[field_name] = candidate
    return base.model_copy(update={"project_id": project_id, **updates})
