import json

import pytest

from pptmaker.projects import ProjectCreate, ProjectRepository
from pptmaker.projects.portability import (
    InvalidProjectImport,
    export_project,
    import_project,
)


def test_export_import_preserves_project_semantics(tmp_path):
    source = ProjectRepository(tmp_path / "source.db")
    target = ProjectRepository(tmp_path / "target.db")
    project = source.create(
        ProjectCreate(name="Demo", last_provider_preset="deepseek")
    )

    imported = import_project(export_project(project), target)

    assert imported.id != project.id
    assert imported.name == project.name
    assert imported.business_state == project.business_state
    assert imported.execution_state == project.execution_state
    assert imported.last_provider_preset == project.last_provider_preset
    assert imported.created_at == project.created_at
    assert imported.updated_at == project.updated_at


def test_export_never_contains_provider_credentials(tmp_path):
    repository = ProjectRepository(tmp_path / "projects.db")
    project = repository.create(ProjectCreate(name="Demo"))

    encoded = export_project(project)

    assert b"api_key" not in encoded.lower()
    assert b"TEST_KEY" not in encoded


def test_imported_running_project_becomes_recoverable(tmp_path):
    source = ProjectRepository(tmp_path / "source.db")
    target = ProjectRepository(tmp_path / "target.db")
    project = source.create(
        ProjectCreate(name="Running", execution_state="RUNNING")
    )

    imported = import_project(export_project(project), target)

    assert imported.execution_state == "FAILED_RECOVERABLE"


def test_export_import_preserves_m2_business_state(tmp_path):
    source = ProjectRepository(tmp_path / "source.db")
    target = ProjectRepository(tmp_path / "target.db")
    project = source.create(
        ProjectCreate(name="Interview", business_state="WAITING_FOR_USER")
    )

    imported = import_project(export_project(project), target)

    assert imported.business_state == "WAITING_FOR_USER"


def test_export_import_preserves_web_policy(tmp_path):
    source = ProjectRepository(tmp_path / "source.db")
    target = ProjectRepository(tmp_path / "target.db")
    project = source.create(ProjectCreate(name="Web", web_policy="NEVER"))

    imported = import_project(export_project(project), target)

    assert imported.web_policy == "NEVER"


def test_export_import_preserves_asset_license_mode(tmp_path):
    source = ProjectRepository(tmp_path / "source-assets.db")
    project = source.create(
        ProjectCreate(name="Assets", asset_license_mode="LOOSE")
    )
    target = ProjectRepository(tmp_path / "target-assets.db")

    imported = import_project(export_project(project), target)

    assert imported.asset_license_mode == "LOOSE"


@pytest.mark.parametrize(
    "payload",
    [
        json.dumps({"schema_version": 1, "value": "x" * (1024 * 1024 + 1)}).encode(),
        json.dumps({"schema_version": 1, **{str(i): i for i in range(10_001)}}).encode(),
    ],
    ids=["long-string", "too-many-keys"],
)
def test_import_rejects_resource_abuse(payload, tmp_path):
    repository = ProjectRepository(tmp_path / "projects.db")

    with pytest.raises(InvalidProjectImport):
        import_project(payload, repository)

    assert repository.list() == []


def test_import_rejects_deep_or_unknown_schema(tmp_path):
    repository = ProjectRepository(tmp_path / "projects.db")
    nested = {}
    current = nested
    for _ in range(21):
        current["child"] = {}
        current = current["child"]

    for payload in (
        json.dumps(nested).encode(),
        json.dumps({"schema_version": 999, "name": "Demo"}).encode(),
    ):
        with pytest.raises(InvalidProjectImport):
            import_project(payload, repository)

    assert repository.list() == []
