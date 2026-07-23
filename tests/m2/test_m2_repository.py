from pptmaker.m2.models import DeckOutline, OutlinePage, RequirementBrief
from pptmaker.m2.repository import M2Repository
from pptmaker.projects import ProjectCreate, ProjectRepository, ProjectUpdate


def page(title: str = "Title") -> OutlinePage:
    return OutlinePage(
        order=1,
        section="Section",
        title=title,
        objective="Explain",
    )


def outline(project_id: str = "p1") -> DeckOutline:
    return DeckOutline(
        project_id=project_id,
        version=1,
        status="DRAFT",
        narrative="Story",
        target_slides=1,
        pages=[page()],
    )


def test_brief_survives_repository_restart(tmp_path):
    path = tmp_path / "pptmaker.db"
    repository = M2Repository(path)
    repository.save_brief(RequirementBrief(project_id="p1"))

    assert M2Repository(path).get_brief("p1") == RequirementBrief(project_id="p1")


def test_approving_new_draft_supersedes_previous_approval(tmp_path):
    repository = M2Repository(tmp_path / "pptmaker.db")
    first = repository.create_outline(outline())
    approved = repository.approve_outline("p1", first.version)
    second = repository.update_outline(approved, pages=[page("Updated")])

    assert repository.get_outline("p1", 1).status == "SUPERSEDED"
    assert second.status == "DRAFT"

    repository.approve_outline("p1", second.version)
    versions = {
        item.version: item.status for item in repository.list_outlines("p1")
    }
    assert versions == {1: "SUPERSEDED", 2: "APPROVED"}


def test_restoring_history_creates_new_draft(tmp_path):
    repository = M2Repository(tmp_path / "pptmaker.db")
    original = repository.create_outline(outline())
    changed = repository.update_outline(original, pages=[page("Changed")])
    restored = repository.restore_outline("p1", original.version)

    assert changed.version == 2
    assert restored.version == 3
    assert restored.parent_version == 1
    assert restored.status == "DRAFT"
    assert restored.pages[0].title == "Title"
    assert repository.get_outline("p1", changed.version).status == "SUPERSEDED"


def test_project_accepts_m2_business_state(tmp_path):
    repository = ProjectRepository(tmp_path / "pptmaker.db")
    project = repository.create(ProjectCreate(name="Demo"))
    updated = repository.update(
        project.id,
        ProjectUpdate(business_state="WAITING_FOR_USER"),
        expected_version=project.version,
    )

    assert updated.business_state == "WAITING_FOR_USER"
