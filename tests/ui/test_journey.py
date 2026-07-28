from pptmaker.m2.models import RequirementBrief, RequirementField
from pptmaker.m2.repository import M2Repository
from pptmaker.projects import ProjectCreate, ProjectRepository
from pptmaker.ui.journey import build_journey


def test_new_project_points_to_requirements(tmp_path):
    projects = ProjectRepository(tmp_path / "pptmaker.db")
    project = projects.create(ProjectCreate(name="Journey"))

    view = build_journey(project.id, projects.path)

    assert [item.status for item in view.stages] == [
        "current",
        "pending",
        "pending",
        "pending",
        "pending",
        "pending",
    ]
    assert "需求分析" in view.next_action


def test_saved_brief_advances_to_outline(tmp_path):
    projects = ProjectRepository(tmp_path / "pptmaker.db")
    project = projects.create(ProjectCreate(name="Journey"))
    M2Repository(projects.path).save_brief(
        RequirementBrief(
            project_id=project.id,
            **{
                name: RequirementField(
                    value="已确认",
                    confidence=1,
                    source="user",
                )
                for name in (
                    "purpose",
                    "scenario",
                    "target_slides",
                    "audience",
                    "priorities",
                    "style",
                )
            },
        )
    )

    view = build_journey(project.id, projects.path)

    assert view.stages[0].status == "complete"
    assert view.stages[1].status == "current"
    assert "概略大纲" in view.next_action
