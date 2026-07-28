from streamlit.testing.v1 import AppTest

from pptmaker.blueprint.repository import BlueprintRepository
from pptmaker.m2.models import DeckOutline, OutlinePage, RequirementBrief
from pptmaker.m2.repository import M2Repository
from pptmaker.m3.repository import M3Repository
from pptmaker.m3.artifacts import GenerationArtifact
from pptmaker.m3.renderer import RenderError
from pptmaker.projects import ProjectCreate, ProjectRepository
from tests.blueprint.factories import blueprint


def _project_with_approved_blueprint(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    projects = ProjectRepository(tmp_path / "pptmaker.db")
    project = projects.create(ProjectCreate(name="P3 Demo"))
    m2 = M2Repository(projects.path)
    m2.save_brief(RequirementBrief(project_id=project.id))
    outline = m2.create_outline(
        DeckOutline(
            project_id=project.id,
            version=1,
            status="DRAFT",
            narrative="Story",
            target_slides=1,
            pages=[
                OutlinePage(
                    id="p1",
                    order=1,
                    section="Value",
                    title="Value is clear",
                    objective="Explain value",
                )
            ],
        )
    )
    approved_outline = m2.approve_outline(project.id, outline.version)
    candidate = blueprint(page_count=1).model_copy(
        update={
            "project_id": project.id,
            "outline_version": approved_outline.version,
        }
    )
    blueprints = BlueprintRepository(projects.path)
    created = blueprints.create(candidate)
    blueprints.approve(project.id, created.version)
    return project, projects, created.version


def test_generation_uses_blueprint_without_api_key_and_persists_download(
    monkeypatch,
    tmp_path,
):
    project, projects, version = _project_with_approved_blueprint(
        monkeypatch, tmp_path
    )
    monkeypatch.setattr(
        "pptmaker.ui.m3_workspace.render_pptx",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RenderError("unavailable")
        ),
    )

    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)
    generate = next(
        item for item in app.button if item.label == "生成 PPT"
    )
    app = generate.click().run(timeout=20)

    assert not app.exception
    assert any(item.label == "下载 PPTX" for item in app.download_button)
    artifact = M3Repository(projects.path).get_artifact(
        project.id, version
    )
    assert artifact.status == "PPTX_READY"
    assert artifact.safe_error_type == "render_unavailable"

    refreshed = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)
    assert any(
        item.label == "下载 PPTX" for item in refreshed.download_button
    )


def test_generation_is_hidden_without_approved_blueprint(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    repository = ProjectRepository(tmp_path / "pptmaker.db")
    repository.create(ProjectCreate(name="No Blueprint"))

    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)

    assert not any(item.label == "生成 PPT" for item in app.button)


def test_interrupted_generation_becomes_recoverable(
    monkeypatch,
    tmp_path,
):
    project, projects, version = _project_with_approved_blueprint(
        monkeypatch, tmp_path
    )
    repository = M3Repository(projects.path)
    repository.save_artifact(
        GenerationArtifact(
            project_id=project.id,
            blueprint_version=version,
            status="RUNNING",
        )
    )

    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)

    assert not app.exception
    assert repository.get_artifact(
        project.id, version
    ).status == "FAILED_RECOVERABLE"
    assert any(item.label == "重新生成 PPT" for item in app.button)
