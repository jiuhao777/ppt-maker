import pytest

from pptmaker.blueprint.repository import BlueprintRepository
from tests.blueprint.factories import blueprint


def test_create_supersedes_previous_draft(tmp_path):
    repository = BlueprintRepository(tmp_path / "db.sqlite")

    first = repository.create(blueprint())
    second = repository.create(blueprint())

    assert repository.get("p1", first.version).status == "SUPERSEDED"
    assert second.version == 2
    assert second.status == "DRAFT"


def test_approve_supersedes_old_approved_version(tmp_path):
    repository = BlueprintRepository(tmp_path / "db.sqlite")
    first = repository.create(blueprint())
    repository.approve("p1", first.version)
    second = repository.create(
        blueprint().model_copy(update={"parent_version": first.version})
    )

    approved = repository.approve("p1", second.version)

    assert approved.status == "APPROVED"
    assert repository.get("p1", first.version).status == "SUPERSEDED"


def test_restore_creates_new_draft(tmp_path):
    repository = BlueprintRepository(tmp_path / "db.sqlite")
    first = repository.create(blueprint())

    restored = repository.restore("p1", first.version)

    assert restored.version == 2
    assert restored.parent_version == first.version
    assert restored.status == "DRAFT"


def test_only_draft_can_be_approved(tmp_path):
    repository = BlueprintRepository(tmp_path / "db.sqlite")
    created = repository.create(blueprint())
    repository.approve("p1", created.version)

    with pytest.raises(ValueError):
        repository.approve("p1", created.version)


def test_list_is_ordered_by_version(tmp_path):
    repository = BlueprintRepository(tmp_path / "db.sqlite")
    repository.create(blueprint())
    repository.create(blueprint())

    assert [item.version for item in repository.list("p1")] == [1, 2]
