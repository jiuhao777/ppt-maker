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
            "生成详细的演示文稿结构大纲。每页包含：标题、页面目标、"
            "核心要点、页面类型、排版布局、配图建议和图标建议。"
            ""
            "layout 从以下类型中选择最合适的（避免全用同一种）："
            "  text — 纯文字段落，适合叙述"
            "  bullets — 要点列表，适合并列信息"
            "  two_column — 双栏，适合文字+要点/配图"
            "  big_number — 数据突出，适合关键指标"
            "  comparison — 左右对比，适合对比分析"
            "  table — 表格，适合结构化数据"
            "  quote — 引用/金句"
            ""
            "image_suggestion：如该页适合配图，填写建议配图方向"
            "（如'中国大模型市场份额对比图'），不需要配图则留空。"
            "icon_suggestion：如该页适合图标点缀，填写图标含义"
            "（如'增长率箭头'、'对勾'），不需要则留空。"
            ""
            "无法由材料支持的内容必须记录为 gaps，不能编造。"
            "verified_facts 中的事实优先于模型记忆；引用时保留其 source_url。"
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
