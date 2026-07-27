import sqlite3
from pathlib import Path

from pptmaker.assets.models import AssetRecord


class AssetRepository:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS assets (
                    project_id TEXT NOT NULL,
                    id TEXT NOT NULL,
                    blueprint_version INTEGER NOT NULL,
                    page_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (project_id, id)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def replace_candidates(
        self,
        project_id: str,
        blueprint_version: int,
        page_id: str,
        records: list[AssetRecord],
    ) -> None:
        if any(
            item.project_id != project_id
            or item.blueprint_version != blueprint_version
            or item.page_id != page_id
            for item in records
        ):
            raise ValueError("asset project, blueprint, or page does not match")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM assets WHERE project_id = ? "
                "AND blueprint_version = ? AND page_id = ? "
                "AND status != 'APPROVED'",
                (project_id, blueprint_version, page_id),
            )
            connection.executemany(
                "INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        item.project_id,
                        item.id,
                        item.blueprint_version,
                        item.page_id,
                        item.status,
                        item.model_dump_json(),
                    )
                    for item in records
                ],
            )

    def list_for_blueprint(
        self,
        project_id: str,
        blueprint_version: int,
        page_id: str | None = None,
    ) -> list[AssetRecord]:
        query = (
            "SELECT payload FROM assets WHERE project_id = ? "
            "AND blueprint_version = ?"
        )
        params: tuple[object, ...] = (project_id, blueprint_version)
        if page_id is not None:
            query += " AND page_id = ?"
            params += (page_id,)
        query += " ORDER BY rowid"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [AssetRecord.model_validate_json(row[0]) for row in rows]

    def approve(self, project_id: str, asset_id: str) -> AssetRecord:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM assets "
                "WHERE project_id = ? AND id = ?",
                (project_id, asset_id),
            ).fetchone()
            if row is None:
                raise KeyError(asset_id)
            selected = AssetRecord.model_validate_json(row[0]).model_copy(
                update={"status": "APPROVED"}
            )
            selected = AssetRecord.model_validate(selected)
            rows = connection.execute(
                "SELECT id, payload FROM assets WHERE project_id = ? "
                "AND blueprint_version = ? AND page_id = ?",
                (
                    project_id,
                    selected.blueprint_version,
                    selected.page_id,
                ),
            ).fetchall()
            for current_id, payload in rows:
                current = AssetRecord.model_validate_json(payload)
                status = "APPROVED" if current_id == asset_id else "REJECTED"
                updated = current.model_copy(update={"status": status})
                connection.execute(
                    "UPDATE assets SET status = ?, payload = ? "
                    "WHERE project_id = ? AND id = ?",
                    (
                        status,
                        updated.model_dump_json(),
                        project_id,
                        current_id,
                    ),
                )
        return selected
