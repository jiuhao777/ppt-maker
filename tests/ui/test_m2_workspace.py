from streamlit.testing.v1 import AppTest

from pptmaker.m2.models import DeckOutline, OutlinePage, RequirementBrief
from pptmaker.m2.repository import M2Repository
from pptmaker.projects import ProjectCreate, ProjectRepository


def test_m2_workspace_shows_task_and_requirement_context(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    project = ProjectRepository(tmp_path / "pptmaker.db").create(
        ProjectCreate(name="M2 Demo")
    )
    M2Repository(tmp_path / "pptmaker.db").save_brief(
        RequirementBrief(project_id=project.id)
    )

    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)

    assert not app.exception
    assert any(item.value == "任务与材料" for item in app.subheader)
    assert any(item.value == "已确认信息" for item in app.subheader)
    assert any(item.label == "不知道/不确定" for item in app.button)


def test_outline_approval_names_exact_version(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    project = ProjectRepository(tmp_path / "pptmaker.db").create(
        ProjectCreate(name="Outline Demo")
    )
    M2Repository(tmp_path / "pptmaker.db").create_outline(
        DeckOutline(
            project_id=project.id,
            version=1,
            status="DRAFT",
            narrative="Story",
            target_slides=1,
            pages=[
                OutlinePage(
                    order=1,
                    section="Intro",
                    title="Opening",
                    objective="Frame the topic",
                )
            ],
        )
    )

    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)

    assert not app.exception
    assert any(item.label == "批准大纲 v1" for item in app.button)
    assert any(item.label == "新增页面" for item in app.button)
