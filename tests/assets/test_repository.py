import pytest

from pptmaker.assets.repository import AssetRepository
from tests.assets.test_models import record


def test_replace_candidates_rejects_cross_project_records(tmp_path):
    repository = AssetRepository(tmp_path / "db.sqlite")

    with pytest.raises(ValueError, match="project"):
        repository.replace_candidates(
            "p1", 1, "page-1", [record(project_id="p2")]
        )


def test_replace_candidates_preserves_approved_asset(tmp_path):
    repository = AssetRepository(tmp_path / "db.sqlite")
    repository.replace_candidates("p1", 1, "page-1", [record()])
    repository.approve("p1", "a1")

    repository.replace_candidates(
        "p1", 1, "page-1", [record(id="a2")]
    )

    assert [item.id for item in repository.list_for_blueprint("p1", 1)] == [
        "a1",
        "a2",
    ]


def test_approve_rejects_other_candidates_for_same_page(tmp_path):
    repository = AssetRepository(tmp_path / "db.sqlite")
    repository.replace_candidates(
        "p1", 1, "page-1", [record(), record(id="a2")]
    )

    approved = repository.approve("p1", "a2")
    records = repository.list_for_blueprint("p1", 1, "page-1")

    assert approved.status == "APPROVED"
    assert {item.id: item.status for item in records} == {
        "a1": "REJECTED",
        "a2": "APPROVED",
    }


def test_list_is_scoped_to_project_blueprint_and_page(tmp_path):
    repository = AssetRepository(tmp_path / "db.sqlite")
    repository.replace_candidates("p1", 1, "page-1", [record()])
    repository.replace_candidates(
        "p1", 1, "page-2", [record(id="a2", page_id="page-2")]
    )
    repository.replace_candidates(
        "p1", 2, "page-1", [record(id="a3", blueprint_version=2)]
    )

    assert [
        item.id
        for item in repository.list_for_blueprint("p1", 1, "page-1")
    ] == ["a1"]
