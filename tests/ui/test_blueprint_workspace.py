from streamlit.testing.v1 import AppTest

from pptmaker.blueprint.models import DeckBlueprint
from pptmaker.blueprint.repository import BlueprintRepository
from pptmaker.m2.models import (
    DeckOutline,
    OutlinePage,
    RequirementBrief,
)
from pptmaker.m2.repository import M2Repository
from pptmaker.projects import ProjectCreate, ProjectRepository
from pptmaker.ui.blueprint_workspace import (
    apply_pending_blueprint_version,
    blueprint_version_label,
    queue_blueprint_version,
)
from tests.blueprint.factories import blueprint


def _approved_outline_project(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    projects = ProjectRepository(tmp_path / "pptmaker.db")
    project = projects.create(ProjectCreate(name="Blueprint Demo"))
    repository = M2Repository(projects.path)
    repository.save_brief(RequirementBrief(project_id=project.id))
    draft = repository.create_outline(
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
    repository.approve_outline(project.id, draft.version)
    return project, projects


def test_approved_outline_shows_blueprint_action(monkeypatch, tmp_path):
    _approved_outline_project(monkeypatch, tmp_path)

    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)

    assert not app.exception
    assert any(
        button.label == "生成详细施工大纲"
        for button in app.button
    )


def test_m3_generation_is_hidden_until_blueprint_approved(
    monkeypatch,
    tmp_path,
):
    _approved_outline_project(monkeypatch, tmp_path)

    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)

    assert not any(button.label == "生成 PPT" for button in app.button)


def test_m3_generation_appears_after_blueprint_approval(
    monkeypatch,
    tmp_path,
):
    project, projects = _approved_outline_project(monkeypatch, tmp_path)
    candidate = blueprint().model_copy(
        update={
            "project_id": project.id,
            "outline_version": 1,
        }
    )
    repository = BlueprintRepository(projects.path)
    created = repository.create(candidate)
    repository.approve(project.id, created.version)

    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)

    assert not app.exception
    assert any(button.label == "生成 PPT" for button in app.button)


def test_pending_blueprint_version_is_applied_before_widget():
    state = {}
    queue_blueprint_version(state, "p1", 2)

    apply_pending_blueprint_version(state, "p1")

    assert state["blueprint_version_p1"] == 2
    assert "blueprint_pending_version_p1" not in state


def test_blueprint_version_label_contains_status():
    candidate: DeckBlueprint = blueprint().model_copy(
        update={"version": 2, "status": "APPROVED"}
    )

    assert blueprint_version_label(candidate) == "v2 · APPROVED"
