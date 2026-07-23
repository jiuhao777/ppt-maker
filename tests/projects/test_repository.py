import pytest

from pptmaker.projects import (
    ProjectCreate,
    ProjectRepository,
    ProjectUpdate,
    VersionConflict,
)


def test_project_crud_survives_repository_restart(tmp_path):
    path = tmp_path / "projects.db"
    repository = ProjectRepository(path)
    created = repository.create(ProjectCreate(name="Demo"))
    updated = repository.update(
        created.id,
        ProjectUpdate(name="Updated"),
        expected_version=created.version,
    )

    reopened = ProjectRepository(path)
    assert reopened.get(created.id).name == "Updated"
    assert reopened.list() == [updated]
    reopened.delete(created.id)
    assert reopened.get(created.id) is None


def test_stale_version_cannot_overwrite_newer_project(tmp_path):
    repository = ProjectRepository(tmp_path / "projects.db")
    project = repository.create(ProjectCreate(name="Demo"))
    repository.update(
        project.id,
        ProjectUpdate(name="New"),
        expected_version=project.version,
    )

    with pytest.raises(VersionConflict):
        repository.update(
            project.id,
            ProjectUpdate(name="Old"),
            expected_version=project.version,
        )
