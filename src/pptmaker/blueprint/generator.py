import json

from pydantic import BaseModel, Field

from pptmaker.blueprint.models import (
    BlueprintPage,
    BlueprintSection,
    DeckBible,
    DeckBlueprint,
)
from pptmaker.blueprint.quality import review_blueprint
from pptmaker.blueprint.layout_planner import plan_page_layout
from pptmaker.m2.models import DeckOutline, RequirementBrief
from pptmaker.m3.models import DesignPlan
from pptmaker.providers.structured import StructuredModel
from pptmaker.research.contracts import FactRecord


class InvalidBlueprint(ValueError):
    pass


class BlueprintSkeleton(BaseModel):
    bible: DeckBible
    sections: list[BlueprintSection] = Field(min_length=1, max_length=20)


class BlueprintPageBatch(BaseModel):
    pages: list[BlueprintPage] = Field(min_length=1, max_length=10)


def _facts_payload(facts: list[FactRecord]) -> list[dict]:
    return [
        {
            "id": fact.id,
            "statement": fact.statement[:2_000],
            "source_title": fact.source_title[:500],
            "source_url": str(fact.source_url),
        }
        for fact in facts
        if not fact.excluded
    ][:100]


def generate_blueprint(
    outline: DeckOutline,
    brief: RequirementBrief,
    facts: list[FactRecord],
    design: DesignPlan,
    model: StructuredModel,
    api_key: str,
    *,
    batch_size: int = 3,
) -> DeckBlueprint:
    if outline.status != "APPROVED":
        raise InvalidBlueprint("overview outline must be approved")
    if batch_size < 1 or batch_size > 10:
        raise ValueError("batch_size must be between 1 and 10")

    active_facts = _facts_payload(facts)
    skeleton = model.generate(
        BlueprintSkeleton,
        (
            "生成演示文稿全局 Deck Bible 和章节结构。"
            "章节必须完整引用 overview 中的现有 page_id，不能新增页面。"
            "颜色不超过一个主色和两个辅助色，字体不超过两种。"
        ),
        json.dumps(
            {
                "requirements": brief.model_dump(mode="json"),
                "overview": outline.model_dump(mode="json"),
                "design": design.model_dump(mode="json"),
                "verified_facts": active_facts,
            },
            ensure_ascii=False,
        ),
        api_key,
    )

    generated_pages = []
    overview_pages = outline.pages
    for start in range(0, len(overview_pages), batch_size):
        requested = overview_pages[start:start + batch_size]
        requested_ids = [page.id for page in requested]
        adjacent = overview_pages[max(0, start - 1):start + batch_size + 1]
        batch = model.generate(
            BlueprintPageBatch,
            (
                "为 requested_pages 生成逐页施工规范。"
                "必须逐一覆盖 requested_page_ids，顺序和 page_id 完全一致。"
                "标题必须表达结论，支撑论点不超过三条。"
                "口头解释写入 speaker_notes。"
                "只允许引用 verified_facts 中的事实 ID。"
                "根据页面目的自动选择视觉类型，不强制使用图片。"
                "每页规划零到四个 asset_slots；每个槽位必须写清"
                "具体图片内容、用途、中文搜索词、角色、是否必需和降级方式。"
                "需要多个品牌标志、案例图或截图时必须拆成独立槽位，"
                "不能合并成模糊的一张配图。"
                "页面正文只保留核心信息，细节写入 detail 或 speaker_notes；"
                "previous_bridge 和 next_bridge 必须说明前后页逻辑。"
                "不要生成 layout_elements 坐标，坐标由系统确定性规划。"
            ),
            json.dumps(
                {
                    "deck_bible": skeleton.bible.model_dump(mode="json"),
                    "sections": [
                        section.model_dump(mode="json")
                        for section in skeleton.sections
                    ],
                    "requested_page_ids": requested_ids,
                    "requested_pages": [
                        page.model_dump(mode="json")
                        for page in requested
                    ],
                    "adjacent_pages": [
                        page.model_dump(mode="json")
                        for page in adjacent
                    ],
                    "verified_facts": active_facts,
                },
                ensure_ascii=False,
            ),
            api_key,
        )
        if [page.page_id for page in batch.pages] != requested_ids:
            raise InvalidBlueprint("page batch does not match requested pages")
        generated_pages.extend(
            plan_page_layout(page) for page in batch.pages
        )

    blueprint = DeckBlueprint(
        project_id=outline.project_id,
        outline_version=outline.version,
        version=1,
        status="DRAFT",
        bible=skeleton.bible,
        sections=skeleton.sections,
        pages=generated_pages,
    )
    review = review_blueprint(
        blueprint,
        {item["id"] for item in active_facts},
    )
    if not review.passed:
        raise InvalidBlueprint(", ".join(review.defects))
    return blueprint
