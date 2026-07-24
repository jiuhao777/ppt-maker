from pathlib import Path

import streamlit as st

from pptmaker.app_paths import database_path
from pptmaker.m2.models import DeckOutline, RequirementBrief
from pptmaker.m2.repository import M2Repository
from pptmaker.m3.builder import build_pptx
from pptmaker.m3.compiler import compile_specs
from pptmaker.m3.content import plan_content
from pptmaker.m3.design import plan_design
from pptmaker.m3.models import ContentPlan, DesignPlan
from pptmaker.m3.renderer import RenderError, render_pptx
from pptmaker.m3.repository import M3Repository
from pptmaker.projects import ProjectRepository
from pptmaker.providers import ProviderConfig, StructuredModel
from pptmaker.providers.structured import StructuredOutputError
from pptmaker.research.repository import ResearchRepository

STYLE_OPTIONS = ["auto", "business", "academic", "creative", "minimal", "tech"]
STYLE_LABELS = {
    "auto": "自动判断", "business": "商务专业", "academic": "学术严谨",
    "creative": "创意活力", "minimal": "极简干净", "tech": "科技未来",
}


def _provider() -> StructuredModel:
    return StructuredModel(ProviderConfig(
        provider_id=st.session_state.provider_id,
        base_url=st.session_state.provider_base_url,
        model=st.session_state.provider_model,
    ))


def render_m3_generation(project, projects: ProjectRepository) -> None:
    m2_repo = M2Repository(projects.path)
    outlines = m2_repo.list_outlines(project.id)
    approved = [o for o in outlines if o.status == "APPROVED"]
    if not approved:
        return

    brief = m2_repo.get_brief(project.id)

    st.divider()
    st.subheader("生成 PPT")

    style = st.selectbox("视觉风格", STYLE_OPTIONS, format_func=STYLE_LABELS.get,
                         key=f"m3_style_{project.id}")

    cache_key = f"m3_pptx_{project.id}"
    thumb_key = f"m3_thumbs_{project.id}"

    if st.button("生成 PPT", key=f"m3_generate_{project.id}", type="primary"):
        if not st.session_state.api_key:
            st.warning("请先输入 API Key。")
            return

        try:
            with st.spinner("设计风格中..."):
                design = plan_design(brief, style, _provider(), st.session_state.api_key)

            with st.spinner("规划内容中..."):
                chunks = m2_repo.list_chunks(project.id)
                facts = ResearchRepository(projects.path).list_facts(project.id, active_only=True)
                content = plan_content(brief, approved[-1], design, chunks, facts,
                                       _provider(), st.session_state.api_key)

            with st.spinner("构建文件中..."):
                specs = compile_specs(content, design)
                export_dir = projects.path.parent / "exports" / project.id
                pptx_path = build_pptx(specs, design, export_dir / f"v{approved[-1].version}.pptx")
                st.session_state[cache_key] = pptx_path.read_bytes()

            with st.spinner("渲染缩略图中..."):
                try:
                    render_dir = projects.path.parent / "renders" / project.id / str(approved[-1].version)
                    thumbs = render_pptx(pptx_path, render_dir)
                    st.session_state[thumb_key] = thumbs
                except RenderError:
                    st.session_state[thumb_key] = []

            m3_repo = M3Repository(projects.path)
            m3_repo.save_design(design)
            m3_repo.save_content(content)

            st.success(f"PPT 生成完成（{len(specs)} 页）")
            st.rerun()

        except StructuredOutputError:
            st.error("模型生成失败，请重试。")

    # Show cached results
    if cache_key in st.session_state:
        st.download_button("下载 PPTX", st.session_state[cache_key],
                           f"{project.id}.pptx", key=f"m3_download_{project.id}")

        thumbs = st.session_state.get(thumb_key, [])
        if thumbs:
            cols = st.columns(3)
            for i, path in enumerate(thumbs):
                with cols[i % 3]:
                    st.image(str(path), caption=f"第 {i + 1} 页", use_container_width=True)
