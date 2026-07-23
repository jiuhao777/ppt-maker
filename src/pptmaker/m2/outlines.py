import json
import re

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
    }
    prompt = json.dumps(evidence, ensure_ascii=False)[:100_000]
    draft = model.generate(
        DeckOutlineDraft,
        (
            "生成结构大纲。每页包含标题、目标、要点、页面类型和来源定位。"
            "无法由材料支持的事实、数据、案例或图片必须记录为 gaps，不能编造。"
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
        "修正结构大纲，但不得增加用户未提出的目标。",
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
    return [
        ResearchTask(
            project_id=outline.project_id,
            outline_version=outline.version,
            question=gap.question,
            page_id=page.id,
            material_type=gap.material_type,
            priority=gap.priority,
            search_hint=gap.search_hint,
        )
        for page in outline.pages
        for gap in page.gaps
    ]
