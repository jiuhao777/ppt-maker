import sqlite3
from collections.abc import MutableMapping
from dataclasses import dataclass

import streamlit as st
from langgraph.types import Command

from pptmaker.app_paths import database_path
from pptmaker.m2.interview import (
    RequirementExtraction,
    accept_unknown,
    extract_requirements_with_freshness,
    plan_next_question,
    remaining_question_count,
)
from pptmaker.m2.materials import ingest_material
from pptmaker.m2.models import (
    ConversationTurn,
    DeckOutline,
    OutlinePage,
    ReworkImpact,
    ReworkRequest,
    RequirementField,
)
from pptmaker.m2.outlines import (
    build_research_tasks,
    diff_outlines,
    generate_outline,
)
from pptmaker.m2.repository import M2Repository
from pptmaker.m2.rework import InvalidRework, analyze_rework, apply_rework
from pptmaker.m2.workflow import build_m2_graph, initial_state
from pptmaker.projects import ProjectRepository, ProjectUpdate
from pptmaker.providers import ProviderConfig, StructuredModel
from pptmaker.providers.structured import StructuredOutputError
from pptmaker.ui.state import safe_generation_message
from pptmaker.blueprint.generator import InvalidBlueprint
from pptmaker.research.bocha import BochaSearch
from pptmaker.research.post_outline import PostOutlineResearch
from pptmaker.research.repository import ResearchRepository
from pptmaker.research.service import (
    FreshnessApprovalRequired,
    FreshnessService,
    SearchKeyRequired,
)
from pptmaker.workflow.foundation import sqlite_checkpointer


ASSUMPTIONS = {
    "purpose": "暂按用户提供的主题确定演示目标，后续验证",
    "scenario": "暂按正式汇报场景设计，后续验证",
    "target_slides": "暂按 10 页规划，后续验证",
    "audience": "暂按一般业务受众设计，后续验证",
    "priorities": "暂按主题的核心问题与结论优先，后续验证",
    "style": "暂按简洁专业风格设计，后续验证",
}


@dataclass(frozen=True)
class WebGenerationBlock:
    blocked: bool
    banner: str = ""
    button_label: str = "分析需求"


def web_generation_block(project, state: MutableMapping) -> WebGenerationBlock:
    if project.web_policy != "ALWAYS":
        return WebGenerationBlock(False)
    if not state.get("bocha_api_key"):
        return WebGenerationBlock(
            True,
            "当前项目要求联网，但尚未配置博查 API Key",
            "请先配置联网搜索",
        )
    if not state.get("bocha_connection_verified"):
        return WebGenerationBlock(
            True,
            "当前项目要求联网，请先测试博查搜索连接",
            "请先测试搜索连接",
        )
    return WebGenerationBlock(False)


def queue_version_selection(
    state: MutableMapping,
    project_id: str,
    version: int,
) -> None:
    state[f"m2_pending_version_{project_id}"] = version


def apply_pending_version(state: MutableMapping, project_id: str) -> None:
    pending_key = f"m2_pending_version_{project_id}"
    if pending_key in state:
        state[f"m2_outline_version_{project_id}"] = state.pop(pending_key)


def outline_version_label(outline: DeckOutline) -> str:
    return (
        f"v{outline.version} · {outline.status} · {outline.creation_method}"
    )


def _provider() -> StructuredModel:
    return StructuredModel(
        ProviderConfig(
            provider_id=st.session_state.provider_id,
            base_url=st.session_state.provider_base_url,
            model=st.session_state.provider_model,
        )
    )


def _set_project_state(
    projects: ProjectRepository,
    project_id: str,
    business_state: str,
) -> None:
    project = projects.get(project_id)
    projects.update(
        project_id,
        ProjectUpdate(business_state=business_state),
        expected_version=project.version,
    )


class WorkspaceServices:
    def __init__(
        self,
        project_id: str,
        projects: ProjectRepository,
        repository: M2Repository,
        api_key: str,
        bocha_key: str = "",
    ):
        self.project_id = project_id
        self.projects = projects
        self.repository = repository
        self.api_key = api_key
        self.bocha_key = bocha_key

    def has_next_question(self, project_id: str) -> bool:
        return plan_next_question(self.repository.get_brief(project_id)) is not None

    def accept_answer(self, project_id: str, answer: object) -> None:
        brief = self.repository.get_brief(project_id)
        question = plan_next_question(brief)
        if isinstance(answer, dict) and answer.get("unknown"):
            brief = accept_unknown(brief, question.field, answer["unknown"])
            content = answer["unknown"]
        else:
            brief = brief.model_copy(
                update={
                    question.field: RequirementField(
                        value=str(answer).strip(),
                        confidence=1,
                        source="user",
                    )
                }
            )
            content = str(answer).strip()
        self.repository.save_brief(brief)
        self.repository.add_turn(
            project_id,
            ConversationTurn(role="user", content=content, field=question.field),
        )

    def generate_outline(self, project_id: str) -> int:
        research = ResearchRepository(self.projects.path)
        run = research.get_latest_run(project_id)
        if run and run.decision.requires_web:
            if run.status in {"PLANNED", "FAILED"}:
                if not self.bocha_key:
                    raise FreshnessApprovalRequired(
                        "需要先联网或确认继续生成非时效性大纲"
                    )
                extraction = RequirementExtraction(
                    brief=self.repository.get_brief(project_id),
                    ai_freshness=run.decision,
                )
                run = FreshnessService(BochaSearch(), research).run(
                    project_id,
                    run.policy,
                    extraction,
                    self.bocha_key,
                    freshness=st.session_state.get(
                        "search_freshness", "oneYear"
                    ),
                )
                if run.status != "COMPLETED":
                    raise FreshnessApprovalRequired(
                        "联网核验失败，需要重试或确认降级"
                    )
        generated = generate_outline(
            self.repository.get_brief(project_id),
            self.repository.list_chunks(project_id),
            _provider(),
            self.api_key,
            facts=research.list_facts(project_id, active_only=True),
        )
        return self.repository.create_outline(generated).version

    def approve_outline(self, project_id: str, version: int) -> int:
        drafts = [
            item
            for item in self.repository.list_outlines(project_id)
            if item.status == "DRAFT"
        ]
        selected = drafts[-1] if drafts else self.repository.get_outline(
            project_id, version
        )
        approved = self.repository.approve_outline(project_id, selected.version)
        tasks = build_research_tasks(approved)
        self.repository.replace_research_tasks(project_id, approved.version, tasks)
        return len(tasks)


def _invoke_graph(project_id, services, value):
    checkpointer = sqlite_checkpointer(
        database_path().with_name("m2-checkpoints.db")
    )
    try:
        graph = build_m2_graph(services, checkpointer)
        config = {"configurable": {"thread_id": project_id}}
        return graph.invoke(value, config)
    finally:
        checkpointer.conn.close()


def _render_materials(project, projects, repository):
    st.subheader("任务与材料")
    description = st.text_area(
        "任务描述或主题",
        key=f"m2_description_{project.id}",
        max_chars=20_000,
    )
    block = web_generation_block(project, st.session_state)
    if block.blocked:
        st.warning(block.banner)
        if st.button(
            "前往 API 设置",
            key=f"m2_open_search_settings_{project.id}",
        ):
            st.session_state.show_search_settings = True
            st.rerun()
    uploads = st.file_uploader(
        "上传 Markdown、DOCX、文本 PDF 或 PPTX",
        type=["md", "docx", "pdf", "pptx", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key=f"m2_uploads_{project.id}",
    )
    _render_research_status(project, projects.path)
    if st.button(
        block.button_label,
        key=f"m2_analyze_{project.id}",
        type="primary",
        disabled=block.blocked,
    ):
        if not st.session_state.api_key:
            st.warning("请先在侧边栏输入 API Key。")
            return
        if not description.strip() and not uploads:
            st.warning("请提供任务描述或材料。")
            return
        chunks = []
        for upload in uploads:
            result = ingest_material(project.id, upload.name, upload.getvalue())
            chunks.extend(result.chunks)
            if result.warning:
                st.warning(f"{upload.name}：{result.warning}")
        repository.save_chunks(project.id, chunks)
        turns = []
        if description.strip():
            turn = ConversationTurn(role="user", content=description.strip())
            repository.add_turn(project.id, turn)
            turns.append(turn)
        extraction = extract_requirements_with_freshness(
            project.id,
            chunks,
            turns,
            _provider(),
            st.session_state.api_key,
            current=repository.get_brief(project.id),
        )
        research = ResearchRepository(projects.path)
        freshness = FreshnessService(BochaSearch(), research)
        if st.session_state.bocha_api_key:
            freshness.run(
                project.id,
                project.web_policy,
                extraction,
                st.session_state.bocha_api_key,
                freshness=st.session_state.get(
                    "search_freshness", "oneYear"
                ),
            )
        else:
            freshness.plan(project.id, project.web_policy, extraction)
        brief = extraction.brief
        repository.save_brief(brief)
        services = WorkspaceServices(
            project.id,
            projects,
            repository,
            st.session_state.api_key,
            st.session_state.bocha_api_key,
        )
        try:
            result = _invoke_graph(
                project.id, services, initial_state(project.id)
            )
        except FreshnessApprovalRequired:
            _set_project_state(projects, project.id, "WAITING_FOR_USER")
            return
        _set_project_state(projects, project.id, result["business_state"])
        st.rerun()


def _render_research_status(project, database):
    repository = ResearchRepository(database)
    run = repository.get_latest_run(project.id)
    if run is None:
        return
    if run.status == "PLANNED":
        st.warning(f"生成概略大纲前需要联网核验：{run.decision.reason}")
        return
    if run.status == "NOT_REQUIRED":
        st.caption(f"未联网：{run.decision.reason}")
        return
    if run.status == "SKIPPED_NO_KEY":
        st.warning("已由用户确认跳过联网；生成内容可能不具有时效性。")
        return
    if run.status == "FAILED":
        st.warning("联网核验失败，已保留离线流程；不会编造最新事实。")
        return
    st.success(f"已完成联网核验：{run.decision.reason}")
    for fact in repository.list_facts(project.id, active_only=True):
        st.markdown(f"[{fact.source_title}]({fact.source_url})")
        published = (
            fact.published_at.date().isoformat()
            if fact.published_at
            else "发布日期未知"
        )
        st.caption(f"{fact.site_name} · {published}")
        if st.button(
            "排除此来源",
            key=f"exclude_fact_{project.id}_{fact.id}",
        ):
            repository.exclude_fact(project.id, fact.id)
            st.rerun()


def _render_interview(project, projects, repository):
    brief = repository.get_brief(project.id)
    if brief is None:
        return
    st.subheader("已确认信息")
    confirmed = {
        name: value.value
        for name in (
            "purpose",
            "scenario",
            "audience",
            "target_slides",
            "priorities",
            "style",
        )
        if (value := getattr(brief, name)).value not in {None, ""}
    }
    st.json(confirmed or {"状态": "尚待确认"})
    st.caption(f"访谈进度：已确认 {len(confirmed)}/6 项")
    question = plan_next_question(brief)
    if question is None:
        st.success("关键需求已确认，可以生成结构大纲。")
        return

    st.markdown(f"**{question.text}**")
    st.caption(question.reason)
    st.caption(f"预计还需约 {remaining_question_count(brief)} 个关键问题")
    with st.form(f"m2_answer_{project.id}_{question.field}"):
        choice = st.radio(
            "建议选项",
            [*question.options, "自行输入"],
            index=None,
        )
        custom_answer = st.text_input("补充或自行输入")
        submitted = st.form_submit_button("提交回答")
    if submitted:
        answer = custom_answer.strip() or (
            choice if choice and choice != "自行输入" else ""
        )
        if not answer.strip():
            st.warning("请输入回答，或选择“不知道/不确定”。")
        elif not st.session_state.api_key:
            st.warning("请先在侧边栏输入 API Key。")
        else:
            services = WorkspaceServices(
                project.id,
                projects,
                repository,
                st.session_state.api_key,
                st.session_state.bocha_api_key,
            )
            try:
                result = _invoke_graph(
                    project.id, services, Command(resume=answer)
                )
            except FreshnessApprovalRequired:
                _set_project_state(
                    projects, project.id, "WAITING_FOR_USER"
                )
                return
            _set_project_state(projects, project.id, result["business_state"])
            st.rerun()
    if st.button(
        "不知道/不确定",
        key=f"m2_unknown_{project.id}_{question.field}",
    ):
        if not st.session_state.api_key:
            st.warning("请先在侧边栏输入 API Key。")
            return
        services = WorkspaceServices(
            project.id,
            projects,
            repository,
            st.session_state.api_key,
            st.session_state.bocha_api_key,
        )
        try:
            result = _invoke_graph(
                project.id,
                services,
                Command(resume={"unknown": ASSUMPTIONS[question.field]}),
            )
        except FreshnessApprovalRequired:
            _set_project_state(projects, project.id, "WAITING_FOR_USER")
            return
        _set_project_state(projects, project.id, result["business_state"])
        st.rerun()


def _render_outline(project, projects, repository):
    outlines = repository.list_outlines(project.id)
    brief = repository.get_brief(project.id)
    if not outlines and brief and plan_next_question(brief) is None:
        run = ResearchRepository(projects.path).get_latest_run(project.id)
        if (
            run
            and run.decision.requires_web
            and run.status in {"PLANNED", "FAILED"}
        ):
            st.warning(
                "该主题需要联网核验。当前没有可用的搜索结果，"
                "继续生成的大纲和内容可能不具有时效性。"
            )
            if st.button(
                "仍然继续生成",
                key=f"m2_accept_stale_{project.id}",
            ):
                FreshnessService(
                    BochaSearch(), ResearchRepository(projects.path)
                ).accept_stale(run)
                st.rerun()
            if st.button(
                "返回配置博查 Key",
                key=f"m2_configure_search_{project.id}",
            ):
                st.session_state.show_search_settings = True
                st.rerun()
            return
        if st.button("生成结构大纲", key=f"m2_generate_{project.id}"):
            if not st.session_state.api_key:
                st.warning("请先在侧边栏输入 API Key。")
                return
            services = WorkspaceServices(
                project.id,
                projects,
                repository,
                st.session_state.api_key,
                st.session_state.bocha_api_key,
            )
            result = _invoke_graph(
                project.id, services, initial_state(project.id)
            )
            _set_project_state(projects, project.id, result["business_state"])
            st.rerun()
        return
    if not outlines:
        return

    st.subheader("结构大纲")
    versions = [item.version for item in outlines]
    by_version = {item.version: item for item in outlines}
    apply_pending_version(st.session_state, project.id)
    selected_version = st.selectbox(
        "大纲版本",
        versions,
        index=len(versions) - 1,
        format_func=lambda value: outline_version_label(by_version[value]),
        key=f"m2_outline_version_{project.id}",
    )
    selected = repository.get_outline(project.id, selected_version)
    if selected.parent_version:
        parent = repository.get_outline(project.id, selected.parent_version)
        difference = diff_outlines(parent, selected)
        st.caption(
            f"相对 v{parent.version}：新增 {len(difference.added_page_ids)} 页，"
            f"删除 {len(difference.deleted_page_ids)} 页，"
            f"移动 {len(difference.moved_page_ids)} 页，"
            f"改标题 {len(difference.title_changes)} 页"
        )

    if selected.status == "DRAFT":
        with st.form(f"m2_outline_editor_{project.id}_{selected.version}"):
            narrative = st.text_area("叙事主线", value=selected.narrative)
            edited = []
            for page in selected.pages:
                with st.expander(f"第 {page.order} 页 · {page.title}", expanded=True):
                    order = st.number_input(
                        "顺序",
                        min_value=1,
                        max_value=100,
                        value=page.order,
                        key=f"m2_order_{selected.version}_{page.id}",
                    )
                    title = st.text_input(
                        "标题",
                        value=page.title,
                        key=f"m2_title_{selected.version}_{page.id}",
                    )
                    objective = st.text_area(
                        "页面目标",
                        value=page.objective,
                        key=f"m2_objective_{selected.version}_{page.id}",
                    )
                    section = st.text_input(
                        "章节",
                        value=page.section,
                        key=f"m2_section_{selected.version}_{page.id}",
                    )
                    key_points = st.text_area(
                        "核心要点（每行一条）",
                        value="\n".join(page.key_points),
                        key=f"m2_points_{selected.version}_{page.id}",
                    )
                    layout = st.selectbox(
                        "排版方式",
                        ["text", "bullets", "two_column", "big_number", "comparison", "table", "quote"],
                        index=["text","bullets","two_column","big_number","comparison","table","quote"].index(page.layout) if page.layout in ["text","bullets","two_column","big_number","comparison","table","quote"] else 0,
                        format_func={"text":"正文","bullets":"要点","two_column":"双栏","big_number":"大字","comparison":"对比","table":"表格","quote":"引用"}.get,
                        key=f"m2_layout_{selected.version}_{page.id}",
                    )
                    visual_detail = st.text_area(
                        "排版细节",
                        value=page.visual_detail,
                        key=f"m2_visual_{selected.version}_{page.id}",
                    )
                    image_suggestion = st.text_input(
                        "配图要求",
                        value=page.image_suggestion,
                        key=f"m2_img_{selected.version}_{page.id}",
                    )
                    logical_bridge = st.text_input(
                        "逻辑衔接",
                        value=page.logical_bridge,
                        key=f"m2_bridge_{selected.version}_{page.id}",
                    )
                    is_memory_anchor = st.checkbox(
                        "记忆锚点",
                        value=page.is_memory_anchor,
                        key=f"m2_memory_{selected.version}_{page.id}",
                    )
                    remove = st.checkbox(
                        "删除此页",
                        key=f"m2_remove_{selected.version}_{page.id}",
                    )
                    if not remove:
                        edited.append(
                            page.model_copy(
                                update={
                                    "order": order,
                                    "title": title,
                                    "objective": objective,
                                    "section": section,
                                    "layout": layout,
                                    "visual_detail": visual_detail,
                                    "image_suggestion": image_suggestion,
                                    "logical_bridge": logical_bridge,
                                    "is_memory_anchor": is_memory_anchor,
                                    "key_points": [
                                        item.strip()
                                        for item in key_points.splitlines()
                                        if item.strip()
                                    ],
                                }
                            )
                        )
            saved = st.form_submit_button("保存为新版本")
        if saved:
            if not edited:
                st.warning("大纲至少保留一页。")
            else:
                edited.sort(key=lambda item: item.order)
                edited = [
                    item.model_copy(update={"order": index})
                    for index, item in enumerate(edited, start=1)
                ]
                created = repository.update_outline(
                    selected,
                    narrative=narrative,
                    target_slides=len(edited),
                    pages=edited,
                )
                queue_version_selection(
                    st.session_state, project.id, created.version
                )
                st.rerun()

        if st.button(
            "新增页面",
            key=f"m2_add_page_{project.id}_{selected.version}",
        ):
            pages = [
                *selected.pages,
                OutlinePage(
                    order=len(selected.pages) + 1,
                    section="新章节",
                    title="新页面",
                    objective="请填写页面目标",
                ),
            ]
            created = repository.update_outline(
                selected,
                target_slides=len(pages),
                pages=pages,
            )
            queue_version_selection(
                st.session_state, project.id, created.version
            )
            st.rerun()

        if st.button(
            f"批准大纲 v{selected.version}",
            key=f"m2_approve_{project.id}_{selected.version}",
            type="primary",
        ):
            services = WorkspaceServices(
                project.id,
                projects,
                repository,
                st.session_state.api_key,
                st.session_state.bocha_api_key,
            )
            result = _invoke_graph(
                project.id, services, Command(resume="approve")
            )
            _set_project_state(projects, project.id, result["business_state"])
            st.rerun()
    else:
        st.info(f"该版本状态：{selected.status}")
        if st.button(
            "恢复为新草稿",
            key=f"m2_restore_{project.id}_{selected.version}",
        ):
            created = repository.restore_outline(project.id, selected.version)
            queue_version_selection(
                st.session_state, project.id, created.version
            )
            _set_project_state(projects, project.id, "OUTLINE_REVIEW")
            st.rerun()

    _render_rework(project, projects, repository, selected)

    approved = [item for item in outlines if item.status == "APPROVED"]
    if approved:
        tasks = repository.list_research_tasks(
            project.id, approved[-1].version
        )
        st.caption(f"已生成 {len(tasks)} 项联网研究任务。")
        research_repository = ResearchRepository(projects.path)
        run = research_repository.get_latest_run(project.id)
        if (
            run is not None
            and run.decision.requires_web
            and run.status != "COMPLETED"
        ):
            if st.button(
                "执行联网研究",
                key=f"m2_run_research_{project.id}_{approved[-1].version}",
                type="primary",
            ):
                try:
                    PostOutlineResearch(
                        BochaSearch(), research_repository
                    ).run(
                        project.id,
                        approved[-1],
                        project.web_policy,
                        run.decision,
                        st.session_state.bocha_api_key,
                        freshness=st.session_state.get(
                            "search_freshness", "oneYear"
                        ),
                    )
                except SearchKeyRequired:
                    st.warning("请先在 API 设置中填写并验证博查 API Key。")
                    return
                st.rerun()


def _render_rework(project, projects, repository, selected):
    st.markdown("#### AI 返工")
    mode = st.radio(
        "返工范围",
        ["global", "local"],
        format_func={"global": "全局返工", "local": "局部返工"}.get,
        horizontal=True,
        key=f"m2_rework_mode_{project.id}_{selected.version}",
    )
    page_labels = {
        page.id: f"第 {page.order} 页 · {page.title}"
        for page in selected.pages
    }
    selected_pages = []
    if mode == "local":
        selected_pages = st.multiselect(
            "选择需要修改的页面",
            list(page_labels),
            format_func=page_labels.get,
            key=f"m2_rework_pages_{project.id}_{selected.version}",
        )
    feedback = st.text_area(
        "修改意见",
        key=f"m2_rework_feedback_{project.id}_{selected.version}",
        max_chars=2_000,
    )
    impact_key = f"m2_rework_impact_{project.id}"
    if st.button(
        "分析影响范围",
        key=f"m2_analyze_rework_{project.id}_{selected.version}",
    ):
        if not st.session_state.api_key:
            st.warning("请先在侧边栏输入 API Key。")
        elif not feedback.strip():
            st.warning("请填写修改意见。")
        elif mode == "local" and not selected_pages:
            st.warning("局部返工至少选择一页。")
        else:
            request = ReworkRequest(
                mode=mode,
                feedback=feedback.strip(),
                selected_page_ids=selected_pages,
            )
            impact = analyze_rework(
                selected,
                request,
                _provider(),
                st.session_state.api_key,
                facts=ResearchRepository(projects.path).list_facts(
                    project.id,
                    active_only=True,
                ),
            )
            st.session_state[impact_key] = {
                "source_version": selected.version,
                "impact": impact.model_dump(mode="json"),
            }
            st.rerun()

    preview = st.session_state.get(impact_key)
    if not preview or preview["source_version"] != selected.version:
        return
    impact = ReworkImpact.model_validate(preview["impact"])
    st.caption("预计影响页面：")
    for page_id in impact.impacted_page_ids:
        st.write(f"- {page_labels[page_id]}：{impact.reasons[page_id]}")
    if st.button(
        "确认并生成新版本",
        key=f"m2_confirm_rework_{project.id}_{selected.version}",
        type="primary",
    ):
        draft = apply_rework(
            selected,
            repository.get_brief(project.id),
            repository.list_chunks(project.id),
            impact,
            _provider(),
            st.session_state.api_key,
            facts=ResearchRepository(projects.path).list_facts(
                project.id,
                active_only=True,
            ),
        )
        created = repository.commit_rework(
            selected,
            draft,
            impact,
            repository.get_brief(project.id),
        )
        st.session_state.pop(impact_key, None)
        queue_version_selection(st.session_state, project.id, created.version)
        _set_project_state(projects, project.id, "OUTLINE_REVIEW")
        st.rerun()
    if st.button(
        "取消返工",
        key=f"m2_cancel_rework_{project.id}_{selected.version}",
    ):
        st.session_state.pop(impact_key, None)
        st.rerun()


def render_m2_workspace(
    project,
    projects: ProjectRepository,
) -> None:
    repository = M2Repository(projects.path)
    try:
        _render_materials(project, projects, repository)
        st.divider()
        _render_interview(project, projects, repository)
        _render_outline(project, projects, repository)
        approved = [
            item
            for item in repository.list_outlines(project.id)
            if item.status == "APPROVED"
        ]
        if approved:
            from pptmaker.ui.blueprint_workspace import (
                render_blueprint_workspace,
            )
            render_blueprint_workspace(project, projects, approved[-1])
        from pptmaker.ui.m3_workspace import render_m3_generation
        render_m3_generation(project, projects)
    except StructuredOutputError as exc:
        st.error(safe_generation_message(exc))
    except InvalidRework as exc:
        st.error(str(exc))
    except InvalidBlueprint:
        st.error("详细大纲未通过质量检查，请调整后重试。")
    except sqlite3.Error:
        st.error("本地数据保存失败，请重试。")
