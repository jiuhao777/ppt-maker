import pytest

from pptmaker.assets.repository import AssetRepository
from pptmaker.blueprint.repository import BlueprintRepository
from tests.assets.test_models import record
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


def test_approve_requires_asset_bound_to_blueprint_page(tmp_path):
    path = tmp_path / "db.sqlite"
    repository = BlueprintRepository(path)
    draft = blueprint(page_count=1)
    draft = draft.model_copy(
        update={
            "pages": [
                draft.pages[0].model_copy(update={"asset_ids": ["a1"]})
            ]
        }
    )
    created = repository.create(draft)

    with pytest.raises(ValueError, match="asset"):
        repository.approve("p1", created.version)

    assets = AssetRepository(path)
    assets.replace_candidates(
        "p1",
        created.version,
        "p1",
        [record(blueprint_version=created.version, page_id="p1")],
    )
    assets.approve("p1", "a1")

    assert repository.approve("p1", created.version).status == "APPROVED"


def test_select_asset_updates_only_draft_page(tmp_path):
    path = tmp_path / "db.sqlite"
    repository = BlueprintRepository(path)
    created = repository.create(blueprint(page_count=1))
    assets = AssetRepository(path)
    assets.replace_candidates(
        "p1", created.version, "p1", [record(page_id="p1")]
    )
    assets.approve("p1", "a1")

    updated = repository.select_asset(
        "p1", created.version, "p1", "a1"
    )

    assert updated.pages[0].asset_ids == ["a1"]


def test_set_page_no_image_clears_asset_and_visual_kind(tmp_path):
    repository = BlueprintRepository(tmp_path / "db.sqlite")
    draft = blueprint(page_count=1)
    draft = draft.model_copy(
        update={
            "pages": [
                draft.pages[0].model_copy(update={"asset_ids": ["old"]})
            ]
        }
    )
    created = repository.create(draft)

    updated = repository.set_page_no_image(
        "p1", created.version, "p1"
    )

    assert updated.pages[0].asset_ids == []
    assert updated.pages[0].visual.kind == "none"


def test_image_page_without_asset_approves_as_no_image_layout(tmp_path):
    repository = BlueprintRepository(tmp_path / "db.sqlite")
    draft = blueprint(page_count=1)
    draft = draft.model_copy(
        update={
            "pages": [
                draft.pages[0].model_copy(
                    update={
                        "visual": draft.pages[0].visual.model_copy(
                            update={"kind": "photo"}
                        )
                    }
                )
            ]
        }
    )
    created = repository.create(draft)

    approved = repository.approve("p1", created.version)
    assert approved.pages[0].visual.kind == "none"
