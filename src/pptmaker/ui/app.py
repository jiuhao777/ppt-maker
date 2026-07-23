import streamlit as st

from pptmaker.app_paths import database_path
from pptmaker.logging_config import configure_logging
from pptmaker.projects import (
    DuplicateProjectName,
    ProjectCreate,
    ProjectRepository,
    ProjectUpdate,
)
from pptmaker.projects.portability import (
    InvalidProjectImport,
    export_project,
    import_project,
)
from pptmaker.providers import PRESETS, OpenAICompatibleProvider, ProviderConfig
from pptmaker.ui.state import initialize_session_state
from pptmaker.workflow import reconcile_interrupted_projects


def _apply_provider_preset() -> None:
    preset = PRESETS[st.session_state.provider_id]
    st.session_state.provider_base_url = preset.base_url
    st.session_state.provider_model = preset.model


def _provider_settings() -> None:
    st.subheader("模型服务")
    st.caption("API Key 仅保存在当前标签页内存中，刷新或关闭后清除。")
    st.selectbox(
        "服务商",
        list(PRESETS),
        format_func={
            "deepseek": "DeepSeek",
            "kimi": "Kimi",
            "qwen": "通义千问",
            "custom": "自定义兼容接口",
        }.get,
        key="provider_id",
        on_change=_apply_provider_preset,
    )
    with st.form("provider_settings"):
        st.text_input("Base URL", key="provider_base_url")
        st.text_input("模型", key="provider_model")
        st.text_input("API Key", type="password", key="api_key")
        test_connection = st.form_submit_button(
            "测试连接", icon=":material/network_check:", type="primary"
        )
    if test_connection:
        if not st.session_state.api_key:
            st.warning("请先输入 API Key。")
            return
        config = ProviderConfig(
            provider_id=st.session_state.provider_id,
            base_url=st.session_state.provider_base_url,
            model=st.session_state.provider_model,
        )
        report = OpenAICompatibleProvider(config).probe(st.session_state.api_key)
        if report.status == "failed":
            st.error(report.error.message)
        else:
            st.success("连接成功，能力探测已完成。")
            for warning in report.warnings:
                st.warning(warning)


def _create_and_import(repository: ProjectRepository) -> None:
    with st.container(border=True):
        st.subheader("新建项目")
        with st.form("create_project"):
            name = st.text_input("项目名称", max_chars=200)
            submitted = st.form_submit_button(
                "创建项目", icon=":material/add:", type="primary"
            )
        if submitted:
            if not name.strip():
                st.warning("请输入项目名称。")
            else:
                try:
                    project = repository.create(ProjectCreate(name=name.strip()))
                    st.session_state.selected_project_id = project.id
                    st.rerun()
                except DuplicateProjectName:
                    st.warning("项目名称已存在，请使用其他名称。")

    with st.container(border=True):
        st.subheader("导入项目")
        uploaded = st.file_uploader("选择项目 JSON", type=["json"])
        if st.button("导入", icon=":material/upload:", disabled=uploaded is None):
            try:
                project = import_project(uploaded.getvalue(), repository)
                st.session_state.selected_project_id = project.id
                st.rerun()
            except InvalidProjectImport:
                st.error("项目文件无效或超过安全限制。")
            except DuplicateProjectName:
                st.warning("同名项目已存在，无法导入。")


def _delete_project(repository: ProjectRepository, project_id: str) -> None:
    repository.delete(project_id)
    st.session_state.selected_project_id = None


def _project_workspace(repository: ProjectRepository) -> None:
    projects = repository.list()
    if not projects:
        st.info("还没有项目，请先创建或导入一个项目。")
        return
    ids = [project.id for project in projects]
    if st.session_state.selected_project_id not in ids:
        st.session_state.selected_project_id = ids[0]
    selected_id = st.selectbox(
        "当前项目",
        ids,
        format_func=lambda project_id: next(
            project.name for project in projects if project.id == project_id
        ),
        key="selected_project_id",
    )
    project = repository.get(selected_id)

    with st.container(border=True):
        st.subheader(project.name)
        st.caption(
            f"业务状态：{project.business_state} · 执行状态：{project.execution_state}"
        )
        if project.execution_state == "RUNNING":
            st.warning("任务运行时请勿刷新；刷新后需重新输入 API Key。")

        provider_ids = list(PRESETS)
        current = (
            project.last_provider_preset
            if project.last_provider_preset in provider_ids
            else st.session_state.provider_id
        )
        selected_provider = st.selectbox(
            "项目默认模型服务",
            provider_ids,
            index=provider_ids.index(current),
            key=f"project_provider_{project.id}",
        )
        if st.button("保存项目设置", icon=":material/save:"):
            repository.update(
                project.id,
                ProjectUpdate(last_provider_preset=selected_provider),
                expected_version=project.version,
            )
            st.success("项目设置已保存。")

        st.download_button(
            "导出 JSON",
            data=export_project(project),
            file_name=f"{project.name}.json",
            mime="application/json",
            icon=":material/download:",
        )

        confirmed = st.checkbox(
            "确认删除此项目", key=f"confirm_delete_{project.id}"
        )
        st.button(
            "删除项目",
            icon=":material/delete:",
            disabled=not confirmed,
            type="secondary",
            on_click=_delete_project,
            args=(repository, project.id),
        )


def main() -> None:
    st.set_page_config(page_title="PPT Maker", page_icon=":material/slideshow:")
    configure_logging()
    initialize_session_state(st.session_state)
    repository = ProjectRepository(database_path())
    if not st.session_state.startup_reconciled:
        reconcile_interrupted_projects(repository)
        st.session_state.startup_reconciled = True

    with st.sidebar:
        _provider_settings()

    st.title("PPT Maker")
    st.caption("本地 AI 演示文稿工作区")
    _create_and_import(repository)
    st.divider()
    st.subheader("项目工作区")
    _project_workspace(repository)


if __name__ == "__main__":
    main()
