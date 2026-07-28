from collections.abc import MutableMapping

import streamlit as st

from pptmaker.assets.curator import AssetCurator, _resolve
from pptmaker.assets.providers import (
    JsonImageProvider,
    OpenverseProvider,
    ProviderChain,
    WikimediaProvider,
)
from pptmaker.assets.repository import AssetRepository
from pptmaker.assets.web_images import (
    BingImageProvider,
    BochaWebImageProvider,
)
from pptmaker.blueprint.generator import generate_blueprint
from pptmaker.blueprint.layout_planner import construction_summary
from pptmaker.blueprint.models import AssetSlot, DeckBlueprint, LayoutRegion
from pptmaker.blueprint.quality import review_blueprint
from pptmaker.blueprint.repository import BlueprintRepository
from pptmaker.m2.models import DeckOutline
from pptmaker.m2.repository import M2Repository
from pptmaker.m3.design import plan_design
from pptmaker.projects import ProjectRepository
from pptmaker.providers import ProviderConfig, StructuredModel
from pptmaker.research.repository import ResearchRepository
from pptmaker.ui.state import safe_generation_message


VISUAL_KINDS = [
    "none",
    "chart",
    "diagram",
    "photo",
    "illustration",
    "icons",
    "cards",
]
STYLE_OPTIONS = [
    "auto",
    "business",
    "academic",
    "creative",
    "minimal",
    "tech",
]


def _curate_assets(
    project, projects, blueprint, page_ids=None, slot_ids=None
):
    providers = []
    if st.session_state.get("bocha_api_key"):
        providers.append(
            BochaWebImageProvider(
                st.session_state.bocha_api_key,
                _resolve,
            )
        )
    providers.extend(
        [
            BingImageProvider(),
            JsonImageProvider(
                "sogou",
                "https://pic.sogou.com/napi/pc/searchList",
            ),
            JsonImageProvider("360", "https://image.so.com/j"),
            JsonImageProvider(
                "baidu",
                "https://image.baidu.com/search/acjson",
            ),
            OpenverseProvider(),
            WikimediaProvider(),
        ]
    )
    result = AssetCurator(
        ProviderChain(providers),
        AssetRepository(projects.path),
        projects.path.parent / "assets",
    ).curate(
        project.id,
        blueprint,
        project.asset_license_mode,
        page_ids=page_ids,
        slot_ids=slot_ids,
    )
    for page_id, diagnostics in result.diagnostics.items():
        st.session_state[
            f"asset_diagnostics_{project.id}_{blueprint.version}_{page_id}"
        ] = diagnostics
    return result


def _render_asset_candidates(
    project,
    projects,
    blueprint_repository,
    blueprint,
):
    assets = AssetRepository(projects.path)
    records = assets.list_for_blueprint(
        project.id, blueprint.version
    )
    by_slot = {}
    for item in records:
        by_slot.setdefault((item.page_id, item.slot_id), []).append(item)
    errors = assets.list_errors(project.id, blueprint.version)

    for page in blueprint.pages:
        page_slots = page.asset_slots
        if not page_slots and page.asset_search_query:
            page_slots = [
                AssetSlot(
                    slot_id="hero",
                    role="hero",
                    subject=page.asset_search_query,
                    search_query=page.asset_search_query,
                    purpose="支撑页面核心结论",
                    region=LayoutRegion(
                        x=0.52, y=0.2, width=0.43, height=0.62
                    ),
                )
            ]
        if not page_slots:
            continue
        st.markdown(f"#### 第 {page.order} 页图片计划")
        for slot in page_slots:
            result_key = f"{page.page_id}:{slot.slot_id}"
            with st.container(border=True):
                st.markdown(f"**{slot.subject}** · {slot.role}")
                st.caption(
                    f"{slot.purpose}｜搜索词：{slot.search_query}｜"
                    f"x={slot.region.x:.0%}, y={slot.region.y:.0%}, "
                    f"宽={slot.region.width:.0%}, 高={slot.region.height:.0%}"
                )
                if result_key in errors:
                    st.warning(errors[result_key])
                diagnostics = st.session_state.get(
                    f"asset_diagnostics_{project.id}_"
                    f"{blueprint.version}_{result_key}"
                )
                if diagnostics:
                    st.caption(
                        "搜索 {searched} · 下载失败 {download_failed} · "
                        "校验拒绝 {validation_rejected} · 可用 {usable}".format(
                            **diagnostics
                        )
                    )
                candidates = by_slot.get(
                    (page.page_id, slot.slot_id), []
                )
                if not candidates:
                    st.info("暂无通过安全验证的候选图片。")
                for item in candidates:
                    if item.local_path:
                        st.image(item.local_path, width=320)
                    if item.status == "APPROVED":
                        st.success("已选择")
                    elif st.button(
                        "选择此图片",
                        key=(
                            f"asset_select_{project.id}_{blueprint.version}_"
                            f"{page.page_id}_{slot.slot_id}_{item.id}"
                        ),
                    ):
                        assets.approve(project.id, item.id)
                        blueprint_repository.select_asset(
                            project.id,
                            blueprint.version,
                            page.page_id,
                            slot.slot_id,
                            item.id,
                        )
                        st.rerun()
                left, right = st.columns(2)
                if left.button(
                    "重新搜索",
                    key=(
                        f"asset_retry_{project.id}_{blueprint.version}_"
                        f"{page.page_id}_{slot.slot_id}"
                    ),
                ):
                    try:
                        _curate_assets(
                            project,
                            projects,
                            blueprint,
                            {page.page_id},
                            {(page.page_id, slot.slot_id)},
                        )
                    except Exception as exc:
                        st.warning(safe_generation_message(exc))
                    else:
                        st.rerun()
                if right.button(
                    "使用降级布局",
                    key=(
                        f"asset_fallback_{project.id}_{blueprint.version}_"
                        f"{page.page_id}_{slot.slot_id}"
                    ),
                ):
                    blueprint_repository.set_slot_fallback(
                        project.id,
                        blueprint.version,
                        page.page_id,
                        slot.slot_id,
                    )
                    st.rerun()


def queue_blueprint_version(
    state: MutableMapping,
    project_id: str,
    version: int,
) -> None:
    state[f"blueprint_pending_version_{project_id}"] = version


def apply_pending_blueprint_version(
    state: MutableMapping,
    project_id: str,
) -> None:
    pending_key = f"blueprint_pending_version_{project_id}"
    if pending_key in state:
        state[f"blueprint_version_{project_id}"] = state.pop(pending_key)


def blueprint_version_label(blueprint: DeckBlueprint) -> str:
    return f"v{blueprint.version} · {blueprint.status}"


def blueprint_version_diff(
    older: DeckBlueprint,
    newer: DeckBlueprint,
) -> list[str]:
    changes = []
    if len(older.pages) != len(newer.pages):
        changes.append(f"页数：{len(older.pages)} → {len(newer.pages)}")
    older_pages = {item.page_id: item for item in older.pages}
    for page in newer.pages:
        previous = older_pages.get(page.page_id)
        if previous is None:
            changes.append(f"新增第 {page.order} 页：{page.conclusion_title}")
            continue
        if previous.conclusion_title != page.conclusion_title:
            changes.append(
                f"第 {page.order} 页标题："
                f"{previous.conclusion_title} → {page.conclusion_title}"
            )
        if previous.page_type != page.page_type:
            changes.append(
                f"第 {page.order} 页类型："
                f"{previous.page_type} → {page.page_type}"
            )
        if previous.asset_slots != page.asset_slots:
            changes.append(f"第 {page.order} 页图片计划已变化")
        if previous.layout_elements != page.layout_elements:
            changes.append(f"第 {page.order} 页布局已变化")
    return changes


def _provider() -> StructuredModel:
    return StructuredModel(
        ProviderConfig(
            provider_id=st.session_state.provider_id,
            base_url=st.session_state.provider_base_url,
            model=st.session_state.provider_model,
        )
    )


def _research_ready(project, projects: ProjectRepository) -> bool:
    if project.web_policy == "NEVER":
        return True
    run = ResearchRepository(projects.path).get_latest_run(project.id)
    return run is not None and run.status in {"COMPLETED", "NOT_REQUIRED"}


def render_blueprint_workspace(
    project,
    projects: ProjectRepository,
    approved_outline: DeckOutline,
) -> None:
    repository = BlueprintRepository(projects.path)
    blueprints = repository.list(project.id)
    facts_repository = ResearchRepository(projects.path)
    active_facts = facts_repository.list_facts(project.id, active_only=True)

    st.divider()
    st.subheader("详细施工大纲")

    if not blueprints:
        style = st.selectbox(
            "详细大纲视觉风格",
            STYLE_OPTIONS,
            key=f"blueprint_style_{project.id}",
        )
        ready = _research_ready(project, projects)
        if not ready:
            st.warning("请先完成联网研究，或明确选择不联网。")
        if st.button(
            "生成详细施工大纲",
            key=f"blueprint_generate_{project.id}",
            type="primary",
            disabled=not ready,
        ):
            if not st.session_state.api_key:
                st.warning("请先在侧边栏输入 API Key。")
                return
            brief = M2Repository(projects.path).get_brief(project.id)
            if brief is None:
                st.warning("请先完成需求分析。")
                return
            try:
                design = plan_design(
                    brief,
                    style,
                    _provider(),
                    st.session_state.api_key,
                )
                draft = generate_blueprint(
                    approved_outline,
                    brief,
                    active_facts,
                    design,
                    _provider(),
                    st.session_state.api_key,
                )
                created = repository.create(draft)
            except Exception as exc:
                st.error(safe_generation_message(exc))
                return
            try:
                _curate_assets(project, projects, created)
            except Exception as exc:
                queue_blueprint_version(
                    st.session_state,
                    project.id,
                    created.version,
                )
                st.warning(
                    "详细大纲已保存，但素材搜索失败。"
                    + safe_generation_message(exc)
                )
                return
            queue_blueprint_version(
                st.session_state,
                project.id,
                created.version,
            )
            st.rerun()
        return

    apply_pending_blueprint_version(st.session_state, project.id)
    versions = [item.version for item in blueprints]
    by_version = {item.version: item for item in blueprints}
    selected_version = st.selectbox(
        "详细大纲版本",
        versions,
        index=len(versions) - 1,
        format_func=lambda version: blueprint_version_label(
            by_version[version]
        ),
        key=f"blueprint_version_{project.id}",
    )
    selected = repository.get(project.id, selected_version)
    st.caption(
        f"基于概略大纲 v{selected.outline_version} · "
        f"{len(selected.sections)} 章 · {len(selected.pages)} 页"
    )
    latest = blueprints[-1]
    if selected.version != latest.version:
        with st.expander(f"与最新版本 v{latest.version} 对比"):
            changes = blueprint_version_diff(selected, latest)
            if changes:
                for change in changes:
                    st.markdown(f"- {change}")
            else:
                st.info("未发现页面结构差异。")

    with st.expander("全局 Deck Bible", expanded=True):
        st.json(selected.bible.model_dump(mode="json"))
    with st.expander("章节结构"):
        for section in selected.sections:
            st.markdown(
                f"**{section.order}. {section.title}** — "
                f"{section.conclusion}"
            )
            st.caption(section.audience_question)

    if selected.status == "DRAFT":
        _render_asset_candidates(
            project,
            projects,
            repository,
            selected,
        )
        known_fact_ids = {fact.id for fact in active_facts}
        with st.form(
            f"blueprint_editor_{project.id}_{selected.version}"
        ):
            narrative = st.text_area(
                "全局叙事主线",
                value=selected.bible.narrative,
            )
            objective = st.text_input(
                "核心目标",
                value=selected.bible.objective,
            )
            action = st.text_input(
                "行动号召",
                value=selected.bible.action,
            )
            edited_pages = []
            for page in selected.pages:
                with st.expander(
                    f"第 {page.order} 页 · {page.conclusion_title}"
                ):
                    st.code(construction_summary(page), language=None)
                    title = st.text_input(
                        "结论式标题",
                        value=page.conclusion_title,
                        key=f"blueprint_title_{selected.version}_{page.page_id}",
                    )
                    message = st.text_area(
                        "一级核心信息",
                        value=page.primary_message,
                        key=f"blueprint_message_{selected.version}_{page.page_id}",
                    )
                    points = st.text_area(
                        "二级支撑论点（每行一条，最多三条）",
                        value="\n".join(page.supporting_points),
                        key=f"blueprint_points_{selected.version}_{page.page_id}",
                    )
                    detail = st.text_area(
                        "三级补充说明",
                        value=page.detail,
                        key=(
                            f"blueprint_detail_{selected.version}_"
                            f"{page.page_id}"
                        ),
                    )
                    notes = st.text_area(
                        "演讲者备注",
                        value=page.speaker_notes,
                        key=f"blueprint_notes_{selected.version}_{page.page_id}",
                    )
                    kind = st.selectbox(
                        "视觉类型",
                        VISUAL_KINDS,
                        index=VISUAL_KINDS.index(page.visual.kind),
                        key=f"blueprint_visual_{selected.version}_{page.page_id}",
                    )
                    layout = st.text_input(
                        "布局",
                        value=page.visual.layout,
                        key=f"blueprint_layout_{selected.version}_{page.page_id}",
                    )
                    previous_bridge = st.text_input(
                        "承接上一页",
                        value=page.previous_bridge,
                        key=f"blueprint_previous_{selected.version}_{page.page_id}",
                    )
                    next_bridge = st.text_input(
                        "引导下一页",
                        value=page.next_bridge,
                        key=f"blueprint_next_{selected.version}_{page.page_id}",
                    )
                    fact_ids = st.multiselect(
                        "引用事实",
                        sorted(known_fact_ids | set(page.fact_ids)),
                        default=page.fact_ids,
                        key=f"blueprint_facts_{selected.version}_{page.page_id}",
                    )
                    edited_slots = []
                    for slot in page.asset_slots:
                        st.markdown(f"**图片槽位：{slot.slot_id}**")
                        subject = st.text_input(
                            "图片内容",
                            value=slot.subject,
                            key=(
                                f"slot_subject_{selected.version}_"
                                f"{page.page_id}_{slot.slot_id}"
                            ),
                        )
                        query = st.text_input(
                            "搜索词",
                            value=slot.search_query,
                            key=(
                                f"slot_query_{selected.version}_"
                                f"{page.page_id}_{slot.slot_id}"
                            ),
                        )
                        purpose = st.text_input(
                            "图片作用",
                            value=slot.purpose,
                            key=(
                                f"slot_purpose_{selected.version}_"
                                f"{page.page_id}_{slot.slot_id}"
                            ),
                        )
                        with st.expander(
                            f"{slot.slot_id} 高级布局设置"
                        ):
                            columns = st.columns(4)
                            x = columns[0].number_input(
                                "x",
                                0.0,
                                1.0,
                                float(slot.region.x),
                                0.01,
                                key=(
                                    f"slot_x_{selected.version}_"
                                    f"{page.page_id}_{slot.slot_id}"
                                ),
                            )
                            y = columns[1].number_input(
                                "y",
                                0.0,
                                1.0,
                                float(slot.region.y),
                                0.01,
                                key=(
                                    f"slot_y_{selected.version}_"
                                    f"{page.page_id}_{slot.slot_id}"
                                ),
                            )
                            width = columns[2].number_input(
                                "宽",
                                0.01,
                                1.0,
                                float(slot.region.width),
                                0.01,
                                key=(
                                    f"slot_w_{selected.version}_"
                                    f"{page.page_id}_{slot.slot_id}"
                                ),
                            )
                            height = columns[3].number_input(
                                "高",
                                0.01,
                                1.0,
                                float(slot.region.height),
                                0.01,
                                key=(
                                    f"slot_h_{selected.version}_"
                                    f"{page.page_id}_{slot.slot_id}"
                                ),
                            )
                        edited_slots.append(
                            slot.model_copy(
                                update={
                                    "subject": subject,
                                    "search_query": query,
                                    "purpose": purpose,
                                    "region": slot.region.model_copy(
                                        update={
                                            "x": x,
                                            "y": y,
                                            "width": width,
                                            "height": height,
                                        }
                                    ),
                                }
                            )
                        )
                    edited_pages.append(
                        page.__class__.model_validate(
                            page.model_dump()
                            | {
                                "conclusion_title": title,
                                "primary_message": message,
                                "supporting_points": [
                                    item.strip()
                                    for item in points.splitlines()
                                    if item.strip()
                                ][:3],
                                "detail": detail,
                                "speaker_notes": notes,
                                "visual": page.visual.model_copy(
                                    update={"kind": kind, "layout": layout}
                                ),
                                "previous_bridge": previous_bridge,
                                "next_bridge": next_bridge,
                                "fact_ids": fact_ids,
                                "asset_slots": [
                                    item.model_dump()
                                    for item in edited_slots
                                ],
                            }
                        )
                    )
            saved = st.form_submit_button("保存详细大纲新版本")
        if saved:
            created = repository.create(
                selected.model_copy(
                    update={
                        "parent_version": selected.version,
                        "change_summary": "手工编辑",
                        "bible": selected.bible.model_copy(
                            update={
                                "narrative": narrative,
                                "objective": objective,
                                "action": action,
                            }
                        ),
                        "pages": edited_pages,
                    }
                )
            )
            queue_blueprint_version(
                st.session_state,
                project.id,
                created.version,
            )
            st.rerun()

        if st.button(
            f"批准详细大纲 v{selected.version}",
            key=f"blueprint_approve_{project.id}_{selected.version}",
            type="primary",
        ):
            review = review_blueprint(selected, known_fact_ids)
            if review.passed:
                try:
                    repository.approve(project.id, selected.version)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.rerun()
            else:
                st.error(
                    "详细大纲未通过质量检查："
                    + "、".join(review.defects)
                )
    else:
        st.info(f"该版本状态：{selected.status}")
        if st.button(
            "恢复详细大纲为新草稿",
            key=f"blueprint_restore_{project.id}_{selected.version}",
        ):
            restored = repository.restore(project.id, selected.version)
            queue_blueprint_version(
                st.session_state,
                project.id,
                restored.version,
            )
            st.rerun()
