import sqlite3
from pathlib import Path

from pptmaker.assets.repository import AssetRepository
from pptmaker.blueprint.migration import load_blueprint
from pptmaker.blueprint.models import DeckBlueprint


class BlueprintRepository:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS blueprints (
                    project_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    outline_version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (project_id, version)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @staticmethod
    def _next_version(
        connection: sqlite3.Connection,
        project_id: str,
    ) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 "
            "FROM blueprints WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return row[0]

    @staticmethod
    def _save(
        connection: sqlite3.Connection,
        blueprint: DeckBlueprint,
    ) -> None:
        connection.execute(
            "INSERT INTO blueprints VALUES (?, ?, ?, ?, ?)",
            (
                blueprint.project_id,
                blueprint.version,
                blueprint.outline_version,
                blueprint.status,
                blueprint.model_dump_json(),
            ),
        )

    @staticmethod
    def _replace_status(
        connection: sqlite3.Connection,
        project_id: str,
        version: int,
        blueprint: DeckBlueprint,
        status: str,
    ) -> DeckBlueprint:
        updated = blueprint.model_copy(update={"status": status})
        connection.execute(
            "UPDATE blueprints SET status = ?, payload = ? "
            "WHERE project_id = ? AND version = ?",
            (status, updated.model_dump_json(), project_id, version),
        )
        return updated

    def create(self, blueprint: DeckBlueprint) -> DeckBlueprint:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT version, payload FROM blueprints "
                "WHERE project_id = ? AND status = 'DRAFT'",
                (blueprint.project_id,),
            ).fetchall()
            for version, payload in rows:
                self._replace_status(
                    connection,
                    blueprint.project_id,
                    version,
                    load_blueprint(payload),
                    "SUPERSEDED",
                )
            created = blueprint.model_copy(
                update={
                    "version": self._next_version(
                        connection,
                        blueprint.project_id,
                    ),
                    "status": "DRAFT",
                }
            )
            self._save(connection, created)
        return created

    def get(self, project_id: str, version: int) -> DeckBlueprint | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM blueprints "
                "WHERE project_id = ? AND version = ?",
                (project_id, version),
            ).fetchone()
        return load_blueprint(row[0]) if row else None

    def list(self, project_id: str) -> list[DeckBlueprint]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM blueprints "
                "WHERE project_id = ? ORDER BY version",
                (project_id,),
            ).fetchall()
        return [load_blueprint(row[0]) for row in rows]

    def approve(self, project_id: str, version: int) -> DeckBlueprint:
        assets = AssetRepository(self.path)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM blueprints "
                "WHERE project_id = ? AND version = ? AND status = 'DRAFT'",
                (project_id, version),
            ).fetchone()
            if row is None:
                raise ValueError("blueprint is not an approvable draft")
            draft = load_blueprint(row[0])
            draft = draft.model_copy(
                update={
                    "pages": [
                        page.model_copy(
                            update={
                                "visual": page.visual.model_copy(
                                    update={"kind": "none"}
                                )
                            }
                        )
                        if (
                            page.visual.kind in {"photo", "illustration"}
                            and not page.asset_ids
                        )
                        else page
                        for page in draft.pages
                    ]
                }
            )
            for page in draft.pages:
                approved_assets = {
                    (item.slot_id, item.id)
                    for item in assets.list_for_blueprint(
                        project_id, version, page.page_id
                    )
                    if item.status == "APPROVED"
                }
                selected_slots = {
                    (item.slot_id, item.selected_asset_id)
                    for item in page.asset_slots
                    if item.selected_asset_id
                }
                legacy_approved = {
                    asset_id
                    for _, asset_id in approved_assets
                }
                if (
                    not set(page.asset_ids).issubset(legacy_approved)
                    or not selected_slots.issubset(approved_assets)
                ):
                    raise ValueError(
                        "blueprint references an unapproved asset"
                    )
            for old_version, payload in connection.execute(
                "SELECT version, payload FROM blueprints "
                "WHERE project_id = ? AND status = 'APPROVED'",
                (project_id,),
            ).fetchall():
                self._replace_status(
                    connection,
                    project_id,
                    old_version,
                    load_blueprint(payload),
                    "SUPERSEDED",
                )
            approved = self._replace_status(
                connection,
                project_id,
                version,
                draft,
                "APPROVED",
            )
        return approved

    def restore(self, project_id: str, version: int) -> DeckBlueprint:
        historical = self.get(project_id, version)
        if historical is None:
            raise KeyError((project_id, version))
        return self.create(
            historical.model_copy(
                update={
                    "status": "DRAFT",
                    "parent_version": version,
                    "change_summary": f"恢复自 v{version}",
                }
            )
        )

    def _update_draft_page(
        self,
        project_id: str,
        version: int,
        page_id: str,
        transform,
    ) -> DeckBlueprint:
        draft = self.get(project_id, version)
        if draft is None or draft.status != "DRAFT":
            raise ValueError("blueprint is not an editable draft")
        if page_id not in {page.page_id for page in draft.pages}:
            raise KeyError(page_id)
        updated = draft.model_copy(
            update={
                "pages": [
                    transform(page) if page.page_id == page_id else page
                    for page in draft.pages
                ]
            }
        )
        with self._connect() as connection:
            connection.execute(
                "UPDATE blueprints SET payload = ? "
                "WHERE project_id = ? AND version = ? AND status = 'DRAFT'",
                (updated.model_dump_json(), project_id, version),
            )
        return updated

    def select_asset(
        self,
        project_id: str,
        version: int,
        page_id: str,
        slot_id: str,
        asset_id: str | None = None,
    ) -> DeckBlueprint:
        if asset_id is None:
            asset_id = slot_id
            slot_id = "hero"
        assets = AssetRepository(self.path)
        approved = {
            (item.slot_id, item.id)
            for item in assets.list_for_blueprint(
                project_id, version, page_id
            )
            if item.status == "APPROVED"
        }
        if (slot_id, asset_id) not in approved:
            raise ValueError("asset is not approved for this page")
        return self._update_draft_page(
            project_id,
            version,
            page_id,
            lambda page: page.model_copy(update={
                "asset_ids": [asset_id],
                "asset_slots": [
                    item.model_copy(update={"selected_asset_id": asset_id})
                    if item.slot_id == slot_id else item
                    for item in page.asset_slots
                ],
            }),
        )

    def set_slot_fallback(
        self,
        project_id: str,
        version: int,
        page_id: str,
        slot_id: str,
    ) -> DeckBlueprint:
        return self._update_draft_page(
            project_id,
            version,
            page_id,
            lambda page: page.model_copy(update={
                "asset_slots": [
                    item.model_copy(
                        update={
                            "selected_asset_id": None,
                            "required": False,
                        }
                    )
                    if item.slot_id == slot_id else item
                    for item in page.asset_slots
                ]
            }),
        )

    def set_page_no_image(
        self,
        project_id: str,
        version: int,
        page_id: str,
    ) -> DeckBlueprint:
        return self._update_draft_page(
            project_id,
            version,
            page_id,
            lambda page: page.model_copy(
                update={
                    "asset_ids": [],
                    "visual": page.visual.model_copy(
                        update={"kind": "none"}
                    ),
                }
            ),
        )
