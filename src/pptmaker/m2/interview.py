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
        ["介绍情况", "争取决策", "推动行动"],
    ),
    "scenario": (
        "这份演示文稿会在什么场景下使用？",
        "为了安排章节节奏和信息密度，需要了解实际演示场景。",
        ["正式汇报", "内部讨论", "对外演示"],
    ),
    "target_slides": (
        "你希望大约制作多少页？",
        "为了控制内容范围和章节分配，需要确定目标页数。",
        ["5–8 页", "9–12 页", "13–20 页"],
    ),
    "audience": (
        "主要受众是谁？",
        "为了选择信息深度和表达方式，需要了解受众。",
        ["管理层", "同事", "客户", "评审"],
    ),
    "priorities": (
        "最希望重点呈现哪些内容？",
        "为了确定页面资源分配，需要明确核心重点。",
        ["成果与数据", "方案与过程", "风险与计划"],
    ),
    "style": (
        "希望整体采用什么表达或视觉风格？",
        "为了让大纲结构与最终呈现方向一致，需要确认风格。",
        ["简洁专业", "数据理性", "生动有感染力"],
    ),
}
SPECIAL_FIELDS = {
    "work_report": ("outcome_metric", "decision_request"),
    "project_report": ("outcome_metric", "main_risk"),
    "pitch": ("funding_goal", "competitive_advantage"),
    "thesis": ("research_method", "main_conclusion"),
    "teaching": ("learner_level", "learning_goal"),
    "data_report": ("time_range", "comparison_baseline"),
    "event": ("call_to_action", "participant_profile"),
    "custom": (),
}
SPECIAL_QUESTIONS = {
    "outcome_metric": ("最重要的成果指标是什么？", "成果指标决定结果页面。", ["进度", "收入", "质量"]),
    "decision_request": ("希望听众做什么决定？", "决策诉求决定结尾。", ["批准", "选择方案", "提供资源"]),
    "main_risk": ("当前最主要的风险是什么？", "主要风险会影响汇报重点。", ["进度", "成本", "质量"]),
    "funding_goal": ("本轮计划融资多少？", "融资目标会改变资金用途页面。", ["500 万以内", "500–2000 万", "2000 万以上"]),
    "competitive_advantage": ("最核心的竞争优势是什么？", "竞争优势决定路演主线。", ["产品", "技术", "渠道"]),
    "research_method": ("主要采用什么研究方法？", "研究方法决定答辩结构。", ["实验", "调查", "案例研究"]),
    "main_conclusion": ("最重要的研究结论是什么？", "核心结论决定内容取舍。", ["已明确", "仍需概括"]),
    "learner_level": ("学习者目前是什么基础？", "基础水平决定讲解深度。", ["零基础", "有基础", "进阶"]),
    "learning_goal": ("学完后希望掌握什么？", "学习目标决定课程结构。", ["理解概念", "掌握方法", "完成实践"]),
    "time_range": ("数据覆盖哪个时间范围？", "时间范围决定数据口径。", ["本月", "本季度", "本年度"]),
    "comparison_baseline": ("数据主要和什么比较？", "比较基准决定图表逻辑。", ["环比", "同比", "目标值"]),
    "call_to_action": ("希望听众采取什么行动？", "行动号召决定宣讲结尾。", ["报名", "参与", "传播"]),
    "participant_profile": ("主要面向哪类参与者？", "参与对象决定信息表达。", ["内部员工", "客户", "公众"]),
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
    for index, field_name in enumerate(SPECIAL_FIELDS[brief.task_type]):
        value = brief.special_requirements.get(field_name, RequirementField())
        if _needs_confirmation(value):
            gaps.append(
                GapCandidate(
                    field=f"special:{field_name}",
                    score=138 - index,
                    blocking=True,
                )
            )
    return sorted(gaps, key=lambda item: item.score, reverse=True)[:8]


def plan_next_question(brief: RequirementBrief) -> InterviewQuestion | None:
    gaps = rank_gaps(brief)
    if not gaps:
        return None
    field_name = gaps[0].field
    if field_name.startswith("special:"):
        text, reason, options = SPECIAL_QUESTIONS[field_name.split(":", 1)[1]]
    else:
        text, reason, options = QUESTIONS[field_name]
    return InterviewQuestion(
        field=field_name,
        text=text,
        reason=reason,
        options=options,
    )


def remaining_question_count(brief: RequirementBrief) -> int:
    return len(rank_gaps(brief))


def accept_unknown(
    brief: RequirementBrief,
    field_name: str,
    assumption: str,
) -> RequirementBrief:
    if field_name.startswith("special:"):
        special_name = field_name.split(":", 1)[1]
        if special_name not in SPECIAL_FIELDS[brief.task_type]:
            raise ValueError("field cannot be assumed")
        special = dict(brief.special_requirements)
        special[special_name] = RequirementField(
            value=assumption,
            confidence=0.25,
            source="assumption",
            assumed=True,
        )
        return brief.model_copy(update={"special_requirements": special})
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
    for field_name in DEFAULT_PRIORITY:
        existing = getattr(base, field_name)
        candidate = getattr(extracted, field_name)
        if existing.source == "user":
            continue
        if not _missing(candidate) and candidate.confidence > existing.confidence:
            updates[field_name] = candidate
    task_type = (
        extracted.task_type
        if base.task_type == "custom" and extracted.task_type != "custom"
        else base.task_type
    )
    allowed_special = SPECIAL_FIELDS[task_type]
    special = dict(base.special_requirements)
    for field_name in allowed_special:
        existing = special.get(field_name, RequirementField())
        candidate = extracted.special_requirements.get(
            field_name, RequirementField()
        )
        if existing.source != "user" and (
            not _missing(candidate) and candidate.confidence > existing.confidence
        ):
            special[field_name] = candidate
    return base.model_copy(
        update={
            "project_id": project_id,
            "task_type": task_type,
            "special_requirements": special,
            **updates,
        }
    )
