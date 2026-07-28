import json

from pptmaker.m2.models import (
    DeckOutline,
    DeckOutlineDraft,
    MaterialChunk,
    RequirementBrief,
    OutlineGap,
    ReworkImpact,
    ReworkRequest,
)
from pptmaker.m2.outlines import reflect_outline
from pptmaker.providers.structured import StructuredModel
from pptmaker.research.contracts import FactRecord


class InvalidRework(ValueError):
    pass


def normalize_rework_draft(
    current: DeckOutline,
    draft: DeckOutlineDraft,
    impact: ReworkImpact,
) -> DeckOutlineDraft:
    impacted = set(impact.impacted_page_ids)
    pages = []
    for index, page in enumerate(draft.pages, start=1):
        if impact.mode == "local" and page.id not in impacted:
            pages.append(page)
            continue
        gaps = list(page.gaps)
        if (
            any(character.isdigit() for character in " ".join(
                [page.title, *page.key_points]
            ))
            and not page.source_locations
            and not gaps
        ):
            gaps.append(
                OutlineGap(
                    question="核验本页数字及其最新来源",
                    material_type="data",
                    priority="high",
                    search_hint="核验页面中的数字、统计口径和发布日期",
                )
            )
        updates = {
            "key_points": page.key_points[:3],
            "gaps": gaps,
        }
        if impact.mode == "global":
            updates["order"] = index
        pages.append(page.model_copy(update=updates))
    return draft.model_copy(
        update={
            "pages": pages,
            "target_slides": (
                len(pages)
                if impact.mode == "global"
                else current.target_slides
            ),
        }
    )


def _validate_impact(
    current: DeckOutline,
    request: ReworkRequest,
    impact: ReworkImpact,
) -> None:
    current_ids = {page.id for page in current.pages}
    impacted = set(impact.impacted_page_ids)
    if impact.mode != request.mode:
        raise InvalidRework("返工影响范围无效")
    if impact.mode == "global":
        if not impacted <= current_ids:
            raise InvalidRework("返工影响范围无效")
    else:
        if not impacted <= current_ids or not set(request.selected_page_ids) <= impacted:
            raise InvalidRework("返工影响范围无效")
    if any(page_id not in impact.reasons for page_id in impacted):
        raise InvalidRework("返工影响范围无效")


def analyze_rework(
    current: DeckOutline,
    request: ReworkRequest,
    model: StructuredModel,
    api_key: str,
    *,
    facts: list[FactRecord] | None = None,
) -> ReworkImpact:
    impact = model.generate(
        ReworkImpact,
        (
            "分析大纲返工影响范围。只能返回现有页面 ID。"
            "局部返工必须包含用户选择页，并说明每个影响理由。"
            "requirement_updates 键名只能是 purpose/audience/scenario/"
            "duration_minutes/target_slides/language/style/priorities/"
            "source_boundary/quality_preference 之一，不得使用其他键名。"
            "verified_facts 中的事实优先于大纲原有内容。"
        ),
        json.dumps(
            {
                "request": request.model_dump(mode="json"),
                "outline": current.model_dump(mode="json"),
                "verified_facts": [
                    {
                        "statement": fact.statement[:2_000],
                        "source_url": str(fact.source_url),
                        "source_title": fact.source_title[:500],
                    }
                    for fact in (facts or [])
                    if not fact.excluded
                ][:100],
            },
            ensure_ascii=False,
        ),
        api_key,
    )
    _validate_impact(current, request, impact)
    return impact


def validate_rework_scope(
    current: DeckOutline,
    draft: DeckOutlineDraft,
    impact: ReworkImpact,
) -> None:
    if impact.mode == "global":
        return
    old_by_id = {page.id: page for page in current.pages}
    new_by_id = {page.id: page for page in draft.pages}
    if set(new_by_id) != set(old_by_id):
        raise InvalidRework("局部返工修改了影响范围外页面")
    impacted = set(impact.impacted_page_ids)
    for page_id, old_page in old_by_id.items():
        if page_id not in impacted and new_by_id[page_id] != old_page:
            raise InvalidRework("局部返工修改了影响范围外页面")


def apply_rework(
    current: DeckOutline,
    brief: RequirementBrief,
    chunks: list[MaterialChunk],
    impact: ReworkImpact,
    model: StructuredModel,
    api_key: str,
    *,
    facts: list[FactRecord] | None = None,
) -> DeckOutlineDraft:
    draft = model.generate(
        DeckOutlineDraft,
        (
            "根据已确认影响范围返工完整大纲。不得残留已替换的主题。"
            "局部返工必须逐字保留影响范围外页面及其页面 ID。"
        ),
        json.dumps(
            {
                "brief": brief.model_dump(mode="json"),
                "outline": current.model_dump(mode="json"),
                "impact": impact.model_dump(mode="json"),
                "materials": [
                    {
                        "source": chunk.source_name,
                        "location": chunk.location,
                        "text": chunk.text[:3_000],
                    }
                    for chunk in chunks[:10]
                ],
                "verified_facts": [
                    {
                        "statement": fact.statement[:2_000],
                        "source_url": str(fact.source_url),
                        "source_title": fact.source_title[:500],
                        "published_at": (
                            fact.published_at.isoformat()
                            if fact.published_at
                            else None
                        ),
                        "accessed_at": fact.accessed_at.isoformat(),
                    }
                    for fact in (facts or [])
                    if not fact.excluded
                ][:100],
            },
            ensure_ascii=False,
        ),
        api_key,
    )
    draft = normalize_rework_draft(current, draft, impact)
    validate_rework_scope(current, draft, impact)
    candidate = DeckOutline(
        project_id=current.project_id,
        version=current.version + 1,
        status="DRAFT",
        parent_version=current.version,
        **draft.model_dump(),
    )
    scope = (
        None
        if impact.mode == "global"
        else set(impact.impacted_page_ids)
    )
    reflection = reflect_outline(
        brief, candidate, scope_page_ids=scope
    )
    if not reflection.passed:
        # one retry with defects
        draft = model.generate(
            DeckOutlineDraft,
            f"修正以下缺陷：{', '.join(reflection.defects)}。"
            "严格遵守 impact；局部返工必须逐字保留影响范围外页面及其页面 ID。"
            "不得增加、删除或重排范围外页面。",
            json.dumps(
                {
                    "current_outline": current.model_dump(mode="json"),
                    "impact": impact.model_dump(mode="json"),
                    "candidate": candidate.model_dump(mode="json"),
                    "defects": reflection.defects,
                },
                ensure_ascii=False,
            ),
            api_key,
        )
        draft = normalize_rework_draft(current, draft, impact)
        validate_rework_scope(current, draft, impact)
        candidate = DeckOutline(
            project_id=current.project_id,
            version=current.version + 1,
            status="DRAFT",
            parent_version=current.version,
            **draft.model_dump(),
        )
        reflection = reflect_outline(
            brief, candidate, scope_page_ids=scope
        )
        if not reflection.passed:
            raise InvalidRework(f"返工结果未通过质量检查: {', '.join(reflection.defects)}")
    return draft
