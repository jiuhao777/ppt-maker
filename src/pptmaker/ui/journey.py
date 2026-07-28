from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pptmaker.assets.repository import AssetRepository
from pptmaker.blueprint.repository import BlueprintRepository
from pptmaker.m2.repository import M2Repository
from pptmaker.m2.interview import plan_next_question
from pptmaker.m3.repository import M3Repository
from pptmaker.research.repository import ResearchRepository


StageStatus = Literal["pending", "current", "complete"]


@dataclass(frozen=True)
class JourneyStage:
    label: str
    status: StageStatus


@dataclass(frozen=True)
class JourneyView:
    stages: tuple[JourneyStage, ...]
    next_action: str


def build_journey(project_id: str, database: Path) -> JourneyView:
    m2 = M2Repository(database)
    outlines = m2.list_outlines(project_id)
    approved_outlines = [item for item in outlines if item.status == "APPROVED"]
    blueprints = BlueprintRepository(database).list(project_id)
    approved_blueprints = [
        item
        for item in blueprints
        if item.status == "APPROVED"
        and approved_outlines
        and item.outline_version == approved_outlines[-1].version
    ]
    blueprint = approved_blueprints[-1] if approved_blueprints else None
    run = ResearchRepository(database).get_latest_run(project_id)
    artifact = (
        M3Repository(database).get_artifact(project_id, blueprint.version)
        if blueprint
        else None
    )

    brief = m2.get_brief(project_id)
    complete = [
        brief is not None and plan_next_question(brief) is None,
        bool(approved_outlines),
        bool(run and run.status in {"COMPLETED", "NOT_REQUIRED", "SKIPPED_NO_KEY"}),
        blueprint is not None,
        _assets_ready(project_id, database, blueprint),
        bool(artifact and artifact.status in {"PPTX_READY", "COMPLETED"}),
    ]
    labels = ("需求", "概略大纲", "联网核验", "详细大纲", "素材", "PPTX")
    first_pending = next((index for index, value in enumerate(complete) if not value), None)
    stages = tuple(
        JourneyStage(
            label,
            "complete" if value else "current" if index == first_pending else "pending",
        )
        for index, (label, value) in enumerate(zip(labels, complete))
    )
    actions = (
        "填写主题或上传材料，开始需求分析。",
        "完成关键问题并批准概略大纲。",
        "执行联网核验，或明确选择不联网。",
        "生成、核对并批准详细施工大纲。",
        "为图片页选择素材，或改为无图版式。",
        "生成并下载可编辑 PPTX。",
    )
    if artifact and artifact.status == "FAILED_RECOVERABLE":
        return JourneyView(stages, "上次生成未完成，请重新生成 PPT。")
    return JourneyView(stages, "全部完成。" if first_pending is None else actions[first_pending])


def _assets_ready(project_id: str, database: Path, blueprint) -> bool:
    if blueprint is None:
        return False
    approved = {
        item.id
        for item in AssetRepository(database).list_for_blueprint(
            project_id, blueprint.version
        )
        if item.status == "APPROVED"
    }
    return all(
        page.visual.kind not in {"photo", "illustration"}
        or bool(set(page.asset_ids) & approved)
        for page in blueprint.pages
    )
