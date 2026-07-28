from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from pptmaker.assets.repository import AssetRepository
from pptmaker.blueprint.repository import BlueprintRepository
from pptmaker.m2.repository import M2Repository
from pptmaker.m3.artifacts import (
    GenerationArtifact,
    file_sha256,
    verified_pptx_path,
)
from pptmaker.m3.blueprint_compiler import (
    compile_blueprint,
    design_from_blueprint,
)
from pptmaker.m3.builder import build_pptx
from pptmaker.m3.quality import inspect_specs
from pptmaker.m3.renderer import render_pptx
from pptmaker.m3.repository import M3Repository
from pptmaker.projects import ProjectRepository
from pptmaker.research.repository import ResearchRepository
from pptmaker.ui.state import safe_generation_message


def render_m3_generation(
    project,
    projects: ProjectRepository,
) -> None:
    outlines = [
        item
        for item in M2Repository(projects.path).list_outlines(project.id)
        if item.status == "APPROVED"
    ]
    if not outlines:
        return
    blueprints = [
        item
        for item in BlueprintRepository(projects.path).list(project.id)
        if item.status == "APPROVED"
        and item.outline_version == outlines[-1].version
    ]
    if not blueprints:
        return
    blueprint = blueprints[-1]
    repository = M3Repository(projects.path)
    recovery_key = f"m3_recovery_checked_{project.id}"
    if not st.session_state.get(recovery_key):
        repository.mark_running_recoverable(project.id)
        st.session_state[recovery_key] = True

    st.divider()
    st.subheader("生成 PPT")
    st.caption(
        f"基于已批准详细大纲 v{blueprint.version}，"
        "生成阶段不会再次调用模型。"
    )

    if st.button(
        "生成 PPT",
        key=f"m3_generate_{project.id}_{blueprint.version}",
        type="primary",
    ):
        now = datetime.now(timezone.utc)
        repository.save_artifact(
            GenerationArtifact(
                project_id=project.id,
                blueprint_version=blueprint.version,
                status="RUNNING",
                created_at=now,
                updated_at=now,
            )
        )
        try:
            with st.spinner("编译详细大纲…"):
                design = design_from_blueprint(blueprint)
                facts = ResearchRepository(projects.path).list_facts(
                    project.id, active_only=True
                )
                assets = AssetRepository(projects.path).list_for_blueprint(
                    project.id, blueprint.version
                )
                specs = compile_blueprint(
                    blueprint, facts, assets, design
                )
                quality = inspect_specs(specs)
                repository.save_design(design)
                repository.save_specs(
                    project.id, blueprint.version, specs
                )
            with st.spinner("构建可编辑 PPTX…"):
                export_dir = projects.path.parent / "exports" / project.id
                pptx_path = build_pptx(
                    specs,
                    design,
                    export_dir
                    / f"blueprint-v{blueprint.version}.pptx",
                )
                ready = GenerationArtifact(
                    project_id=project.id,
                    blueprint_version=blueprint.version,
                    status="PPTX_READY",
                    pptx_path=str(pptx_path),
                    pptx_hash=file_sha256(pptx_path),
                    quality_report=quality,
                    created_at=now,
                    updated_at=datetime.now(timezone.utc),
                )
                repository.save_artifact(ready)
            with st.spinner("PowerPoint 渲染预览…"):
                try:
                    render_dir = (
                        projects.path.parent
                        / "renders"
                        / project.id
                        / str(blueprint.version)
                    )
                    renders = render_pptx(pptx_path, render_dir)
                except Exception:
                    repository.save_artifact(
                        ready.model_copy(
                            update={
                                "safe_error_type": "render_unavailable",
                                "updated_at": datetime.now(timezone.utc),
                            }
                        )
                    )
                else:
                    repository.save_artifact(
                        ready.model_copy(
                            update={
                                "status": "COMPLETED",
                                "render_paths": [
                                    str(path) for path in renders
                                ],
                                "updated_at": datetime.now(timezone.utc),
                            }
                        )
                    )
            st.rerun()
        except Exception as exc:
            repository.save_artifact(
                GenerationArtifact(
                    project_id=project.id,
                    blueprint_version=blueprint.version,
                    status="FAILED_RECOVERABLE",
                    safe_error_type=type(exc).__name__,
                    created_at=now,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            st.error(safe_generation_message(exc))

    artifact = repository.get_artifact(project.id, blueprint.version)
    if artifact is None:
        return
    if artifact.status == "FAILED_RECOVERABLE":
        st.warning("上次生成未完成，可以重新生成。")
        return
    if artifact.status == "RUNNING":
        st.info("生成任务正在执行。")
        return
    try:
        pptx_path = verified_pptx_path(
            artifact, projects.path.parent
        )
    except ValueError:
        st.error("生成文件校验失败，请重新生成。")
        return
    st.download_button(
        "下载 PPTX",
        pptx_path.read_bytes(),
        file_name=f"{project.name}.pptx",
        key=f"m3_download_{project.id}_{blueprint.version}",
    )
    if artifact.safe_error_type == "render_unavailable":
        st.warning("PPTX 已生成，但当前环境无法渲染预览。")
    valid_renders = [
        path
        for value in artifact.render_paths
        if (path := _safe_render_path(value, projects.path.parent))
    ]
    if valid_renders:
        columns = st.columns(3)
        for index, path in enumerate(valid_renders):
            with columns[index % 3]:
                st.image(
                    str(path),
                    caption=f"第 {index + 1} 页",
                    use_container_width=True,
                )


def _safe_render_path(value: str, data_root):
    root = data_root.resolve()
    path = Path(value).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path if path.is_file() else None
