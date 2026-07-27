from collections.abc import MutableMapping

import streamlit as st

from pptmaker.blueprint.generator import generate_blueprint
from pptmaker.blueprint.models import DeckBlueprint
from pptmaker.blueprint.quality import review_blueprint
from pptmaker.blueprint.repository import BlueprintRepository
from pptmaker.m2.models import DeckOutline
from pptmaker.m2.repository import M2Repository
from pptmaker.m3.design import plan_design
from pptmaker.projects import ProjectRepository
from pptmaker.providers import ProviderConfig, StructuredModel
from pptmaker.research.repository import ResearchRepository


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
                    asset_query = st.text_input(
                        "候选素材搜索要求",
                        value=page.asset_search_query,
                        key=f"blueprint_asset_{selected.version}_{page.page_id}",
                    )
                    edited_pages.append(
                        page.model_copy(
                            update={
                                "conclusion_title": title,
                                "primary_message": message,
                                "supporting_points": [
                                    item.strip()
                                    for item in points.splitlines()
                                    if item.strip()
                                ][:3],
                                "speaker_notes": notes,
                                "visual": page.visual.model_copy(
                                    update={"kind": kind, "layout": layout}
                                ),
                                "previous_bridge": previous_bridge,
                                "next_bridge": next_bridge,
                                "fact_ids": fact_ids,
                                "asset_search_query": asset_query,
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
                repository.approve(project.id, selected.version)
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
