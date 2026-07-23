import sqlite3

import streamlit as st
from langgraph.types import Command

from pptmaker.app_paths import database_path
from pptmaker.m2.interview import (
    accept_unknown,
    extract_requirements,
    plan_next_question,
)
from pptmaker.m2.materials import ingest_material
from pptmaker.m2.models import (
    ConversationTurn,
    OutlinePage,
    RequirementField,
)
from pptmaker.m2.outlines import (
    build_research_tasks,
    diff_outlines,
    generate_outline,
)
from pptmaker.m2.repository import M2Repository
from pptmaker.m2.workflow import build_m2_graph, initial_state
from pptmaker.projects import ProjectRepository, ProjectUpdate
from pptmaker.providers import ProviderConfig, StructuredModel
from pptmaker.providers.structured import StructuredOutputError
from pptmaker.workflow.foundation import sqlite_checkpointer


ASSUMPTIONS = {
    "purpose": "暂按用户提供的主题确定演示目标，后续验证",
    "scenario": "暂按正式汇报场景设计，后续验证",
    "target_slides": "暂按 10 页规划，后续验证",
    "audience": "暂按一般业务受众设计，后续验证",
    "priorities": "暂按主题的核心问题与结论优先，后续验证",
    "style": "暂按简洁专业风格设计，后续验证",
}


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
    ):
        self.project_id = project_id
        self.projects = projects
        self.repository = repository
        self.api_key = api_key

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
        generated = generate_outline(
            self.repository.get_brief(project_id),
            self.repository.list_chunks(project_id),
            _provider(),
            self.api_key,
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
    uploads = st.file_uploader(
        "上传 Markdown、DOCX、文本 PDF 或 PPTX",
        type=["md", "docx", "pdf", "pptx", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key=f"m2_uploads_{project.id}",
    )
    if st.button("分析需求", key=f"m2_analyze_{project.id}", type="primary"):
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
        brief = extract_requirements(
            project.id,
            chunks,
            turns,
            _provider(),
            st.session_state.api_key,
            current=repository.get_brief(project.id),
        )
        repository.save_brief(brief)
        services = WorkspaceServices(
            project.id, projects, repository, st.session_state.api_key
        )
        result = _invoke_graph(project.id, services, initial_state(project.id))
        _set_project_state(projects, project.id, result["business_state"])
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
    with st.form(f"m2_answer_{project.id}_{question.field}"):
        answer = st.text_input("你的回答")
        submitted = st.form_submit_button("提交回答")
    if submitted:
        if not answer.strip():
            st.warning("请输入回答，或选择“不知道/不确定”。")
        elif not st.session_state.api_key:
            st.warning("请先在侧边栏输入 API Key。")
        else:
            services = WorkspaceServices(
                project.id, projects, repository, st.session_state.api_key
            )
            result = _invoke_graph(project.id, services, Command(resume=answer))
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
            project.id, projects, repository, st.session_state.api_key
        )
        result = _invoke_graph(
            project.id,
            services,
            Command(resume={"unknown": ASSUMPTIONS[question.field]}),
        )
        _set_project_state(projects, project.id, result["business_state"])
        st.rerun()


def _render_outline(project, projects, repository):
    outlines = repository.list_outlines(project.id)
    brief = repository.get_brief(project.id)
    if not outlines and brief and plan_next_question(brief) is None:
        if st.button("生成结构大纲", key=f"m2_generate_{project.id}"):
            if not st.session_state.api_key:
                st.warning("请先在侧边栏输入 API Key。")
                return
            services = WorkspaceServices(
                project.id, projects, repository, st.session_state.api_key
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
    selected_version = st.selectbox(
        "大纲版本",
        versions,
        index=len(versions) - 1,
        format_func=lambda value: f"v{value}",
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
                repository.update_outline(
                    selected,
                    narrative=narrative,
                    target_slides=len(edited),
                    pages=edited,
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
            repository.update_outline(
                selected,
                target_slides=len(pages),
                pages=pages,
            )
            st.rerun()

        if st.button(
            f"批准大纲 v{selected.version}",
            key=f"m2_approve_{project.id}_{selected.version}",
            type="primary",
        ):
            services = WorkspaceServices(
                project.id, projects, repository, st.session_state.api_key
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
            repository.restore_outline(project.id, selected.version)
            _set_project_state(projects, project.id, "OUTLINE_REVIEW")
            st.rerun()

    approved = [item for item in outlines if item.status == "APPROVED"]
    if approved:
        tasks = repository.list_research_tasks(
            project.id, approved[-1].version
        )
        st.caption(f"已生成 {len(tasks)} 项联网研究任务。")


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
    except StructuredOutputError as exc:
        st.error(str(exc))
    except sqlite3.Error:
        st.error("本地数据保存失败，请重试。")
