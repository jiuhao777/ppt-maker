import json
import re
import unicodedata

from pptmaker.m2.models import (
    DeckOutline,
    DeckOutlineDraft,
    MaterialChunk,
    OutlineDiff,
    ReflectionResult,
    ResearchTask,
    RequirementBrief,
)
from pptmaker.providers.structured import StructuredModel
from pptmaker.research.contracts import FactRecord


def reflect_outline(
    brief: RequirementBrief,
    outline: DeckOutline,
) -> ReflectionResult:
    defects = []
    titles = [" ".join(page.title.lower().split()) for page in outline.pages]
    if len(titles) != len(set(titles)):
        defects.append("duplicate_titles")
    if len(outline.pages) != outline.target_slides:
        defects.append("page_count_mismatch")
    if [page.order for page in outline.pages] != list(
        range(1, len(outline.pages) + 1)
    ):
        defects.append("page_order_invalid")
    requested = brief.target_slides.value
    if isinstance(requested, int) and requested != outline.target_slides:
        defects.append("requested_page_count_mismatch")
    duration = brief.duration_minutes.value
    if (
        isinstance(duration, int)
        and duration > 0
        and outline.target_slides / duration > 2
    ):
        defects.append("duration_density_high")
    if any(
        re.search(r"\d", " ".join([page.title, *page.key_points]))
        and not page.source_locations
        and not page.gaps
        for page in outline.pages
    ):
        defects.append("unsupported_numeric_fact")
    if any(len(page.title) > 40 for page in outline.pages):
        defects.append("title_too_long")
    if any(len(page.key_points) > 3 for page in outline.pages):
        defects.append("too_many_key_points")
    # memory_anchors and narrative_framework are quality signals, not hard errors
    # — they do not block reflection pass or rework.
    return ReflectionResult(passed=not defects, defects=defects)


def generate_outline(
    brief: RequirementBrief,
    chunks: list[MaterialChunk],
    model: StructuredModel,
    api_key: str,
    *,
    facts: list[FactRecord] | None = None,
) -> DeckOutline:
    evidence = {
        "requirements": brief.model_dump(mode="json"),
        "materials": [
            {
                "source": chunk.source_name,
                "location": chunk.location,
                "text": chunk.text,
            }
            for chunk in chunks
        ],
        "verified_facts": [
            {
                "statement": fact.statement,
                "source_url": str(fact.source_url),
                "source_title": fact.source_title,
                "published_at": (
                    fact.published_at.isoformat()
                    if fact.published_at
                    else None
                ),
                "accessed_at": fact.accessed_at.isoformat(),
            }
            for fact in (facts or [])
            if not fact.excluded
        ],
    }
    prompt = json.dumps(evidence, ensure_ascii=False)[:100_000]
    draft = model.generate(
        DeckOutlineDraft,
        (
            "你是一位顶级演示文稿设计师。按以下5层结构生成详细大纲。\n"
            "\n"
            "## 1. 全局锚点\n"
            "- narrative_framework: 选择叙事框架(SCQA/成果-问题-计划/是什么-为什么-怎么做/痛点-方案-价值)\n"
            "- narrative: 一句话叙事主线\n"
            "- global_constraints: 列出全局硬规则(如'单页正文≤100字''禁止大段文字''颜色≤3种')\n"
            "\n"
            "## 2. 叙事结构\n"
            "- 章节划分3-4个，每章明确'解决什么疑问'\n"
            "- target_slides: 根据时长合理分页\n"
            "\n"
            "## 3. 单页精细规范(每页)\n"
            "- title: 必须是结论式标题(≤30字)，不是范畴名\n  ❌'市场分析' ✅'2025年市场规模破100亿'\n"
            "- page_type: 封面/目录/章节过渡/内容/数据/案例/金句/结尾\n"
            "- layout: 见下方类型\n"
            "- key_points: 支撑论点≤3条，每条≤15字\n"
            "- visual_detail: 排版细则(比例/对齐/高亮/留白)\n 如'左3右7分栏，标题左对齐，核心数字83%用主色加粗放大'\n"
            "- image_suggestion: 配图精确要求，禁止模糊描述\n  ❌'放AI图' ✅'扁平化蓝色极简插画，AI生成PPT的办公场景，右侧60%区域'\n"
            "- logical_bridge: 与前一页的逻辑衔接，如'上页讲痛点，本页用数据证明市场规模'\n"
            "- is_memory_anchor: 每3-5页设1个记忆锚点(数字/金句/反差)\n"
            "\n"
            "## 4. 体验节奏\n"
            "- 每3页高密度页配1页轻页(金句/过渡)\n"
            "- 排版穿插(不要所有页同一种layout)\n"
            "- 记忆锚点均匀分布\n"
            "\n"
            "## 5. 质量守则\n"
            "- 每页只讲一个核心结论\n"
            "- 单页正文要点不超过3条\n"
            "- 颜色主色≤3种\n"
            "- 无法由材料或事实支持的内容标记为gaps\n"
        ),
        prompt,
        api_key,
    )
    outline = _to_outline(brief.project_id, draft)
    reflection = reflect_outline(brief, outline)
    if reflection.passed:
        return outline
    corrected = model.generate(
        DeckOutlineDraft,
        "修正结构大纲，但不得增加用户未提出的目标。"
        "保留已有的 layout、image_suggestion 和 icon_suggestion 选择。",
        json.dumps(
            {
                "defects": reflection.defects,
                "outline": draft.model_dump(mode="json"),
            },
            ensure_ascii=False,
        ),
        api_key,
    )
    return _to_outline(brief.project_id, corrected)


def _to_outline(project_id: str, draft: DeckOutlineDraft) -> DeckOutline:
    return DeckOutline(
        project_id=project_id,
        version=1,
        status="DRAFT",
        **draft.model_dump(),
    )


def diff_outlines(old: DeckOutline, new: DeckOutline) -> OutlineDiff:
    old_pages = {page.id: page for page in old.pages}
    new_pages = {page.id: page for page in new.pages}
    return OutlineDiff(
        added_page_ids=[
            page.id for page in new.pages if page.id not in old_pages
        ],
        deleted_page_ids=[
            page.id for page in old.pages if page.id not in new_pages
        ],
        moved_page_ids=[
            page.id
            for page in new.pages
            if page.id in old_pages and old_pages[page.id].order != page.order
        ],
        title_changes={
            page.id: (old_pages[page.id].title, page.title)
            for page in new.pages
            if page.id in old_pages and old_pages[page.id].title != page.title
        },
    )


def build_research_tasks(outline: DeckOutline) -> list[ResearchTask]:
    tasks = [
        ResearchTask(
            project_id=outline.project_id,
            outline_version=outline.version,
            question=gap.question,
            page_id=page.id,
            related_page_ids=[page.id],
            material_type=gap.material_type,
            priority=gap.priority,
            search_hint=gap.search_hint,
        )
        for page in outline.pages
        for gap in page.gaps
    ]
    return deduplicate_research_tasks(tasks)


def _normalized_question(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"[\s?？!！。.,，:：;；]+", "", normalized)


def deduplicate_research_tasks(
    tasks: list[ResearchTask],
) -> list[ResearchTask]:
    priority_order = {"low": 0, "medium": 1, "high": 2}
    merged = {}
    order = []
    for task in tasks:
        key = (_normalized_question(task.question), task.material_type)
        pages = task.related_page_ids or [task.page_id]
        if key not in merged:
            merged[key] = task.model_copy(
                update={"related_page_ids": list(dict.fromkeys(pages))}
            )
            order.append(key)
            continue
        existing = merged[key]
        combined_pages = list(
            dict.fromkeys([*existing.related_page_ids, *pages])
        )
        priority = (
            task.priority
            if priority_order[task.priority] > priority_order[existing.priority]
            else existing.priority
        )
        merged[key] = existing.model_copy(
            update={
                "related_page_ids": combined_pages,
                "priority": priority,
            }
        )
    return [merged[key] for key in order]
