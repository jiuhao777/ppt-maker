import json

from pptmaker.m2.models import (
    DeckOutline,
    DeckOutlineDraft,
    MaterialChunk,
    RequirementBrief,
    ReworkImpact,
    ReworkRequest,
)
from pptmaker.m2.outlines import reflect_outline
from pptmaker.providers.structured import StructuredModel


class InvalidRework(ValueError):
    pass


def _validate_impact(
    current: DeckOutline,
    request: ReworkRequest,
    impact: ReworkImpact,
) -> None:
    current_ids = {page.id for page in current.pages}
    impacted = set(impact.impacted_page_ids)
    if impact.mode != request.mode or not impacted <= current_ids:
        raise InvalidRework("返工影响范围无效")
    if request.mode == "local" and not set(request.selected_page_ids) <= impacted:
        raise InvalidRework("返工影响范围无效")
    if any(page_id not in impact.reasons for page_id in impacted):
        raise InvalidRework("返工影响范围无效")


def analyze_rework(
    current: DeckOutline,
    request: ReworkRequest,
    model: StructuredModel,
    api_key: str,
) -> ReworkImpact:
    impact = model.generate(
        ReworkImpact,
        (
            "分析大纲返工影响范围。只能返回现有页面 ID。"
            "局部返工必须包含用户选择页，并说明每个影响理由。"
        ),
        json.dumps(
            {
                "request": request.model_dump(mode="json"),
                "outline": current.model_dump(mode="json"),
            },
            ensure_ascii=False,
        )[:100_000],
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
                        "text": chunk.text,
                    }
                    for chunk in chunks
                ],
            },
            ensure_ascii=False,
        )[:100_000],
        api_key,
    )
    validate_rework_scope(current, draft, impact)
    candidate = DeckOutline(
        project_id=current.project_id,
        version=current.version + 1,
        status="DRAFT",
        parent_version=current.version,
        **draft.model_dump(),
    )
    reflection = reflect_outline(brief, candidate)
    if not reflection.passed:
        raise InvalidRework("返工结果未通过质量检查")
    return draft
