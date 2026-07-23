import sqlite3
from pathlib import Path

from pptmaker.m2.models import (
    ConversationTurn,
    DeckOutline,
    MaterialChunk,
    ResearchTask,
    RequirementBrief,
)


class M2Repository:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS m2_briefs (
                    project_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS m2_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS m2_materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS m2_outlines (
                    project_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (project_id, version)
                );
                CREATE TABLE IF NOT EXISTS m2_research_tasks (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    outline_version INTEGER NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def save_brief(self, brief: RequirementBrief) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO m2_briefs (project_id, payload) VALUES (?, ?)
                ON CONFLICT(project_id) DO UPDATE SET payload = excluded.payload
                """,
                (brief.project_id, brief.model_dump_json()),
            )

    def get_brief(self, project_id: str) -> RequirementBrief | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM m2_briefs WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return RequirementBrief.model_validate_json(row[0]) if row else None

    def add_turn(self, project_id: str, turn: ConversationTurn) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO m2_turns (project_id, payload) VALUES (?, ?)",
                (project_id, turn.model_dump_json()),
            )

    def list_turns(self, project_id: str) -> list[ConversationTurn]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM m2_turns WHERE project_id = ? ORDER BY id",
                (project_id,),
            ).fetchall()
        return [ConversationTurn.model_validate_json(row[0]) for row in rows]

    def save_chunks(self, project_id: str, chunks: list[MaterialChunk]) -> None:
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO m2_materials (project_id, payload) VALUES (?, ?)",
                [(project_id, chunk.model_dump_json()) for chunk in chunks],
            )

    def list_chunks(self, project_id: str) -> list[MaterialChunk]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM m2_materials WHERE project_id = ? ORDER BY id",
                (project_id,),
            ).fetchall()
        return [MaterialChunk.model_validate_json(row[0]) for row in rows]

    def _next_outline_version(
        self, connection: sqlite3.Connection, project_id: str
    ) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM m2_outlines "
            "WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return row[0]

    @staticmethod
    def _insert_outline(
        connection: sqlite3.Connection, outline: DeckOutline
    ) -> None:
        connection.execute(
            "INSERT INTO m2_outlines VALUES (?, ?, ?, ?)",
            (
                outline.project_id,
                outline.version,
                outline.status,
                outline.model_dump_json(),
            ),
        )

    def create_outline(self, outline: DeckOutline) -> DeckOutline:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            drafts = connection.execute(
                "SELECT version, payload FROM m2_outlines "
                "WHERE project_id = ? AND status = 'DRAFT'",
                (outline.project_id,),
            ).fetchall()
            for old_version, old_payload in drafts:
                superseded = DeckOutline.model_validate_json(
                    old_payload
                ).model_copy(update={"status": "SUPERSEDED"})
                connection.execute(
                    "UPDATE m2_outlines SET status = ?, payload = ? "
                    "WHERE project_id = ? AND version = ?",
                    (
                        superseded.status,
                        superseded.model_dump_json(),
                        outline.project_id,
                        old_version,
                    ),
                )
            version = self._next_outline_version(connection, outline.project_id)
            created = outline.model_copy(
                update={"version": version, "status": "DRAFT"}
            )
            self._insert_outline(connection, created)
        return created

    def get_outline(self, project_id: str, version: int) -> DeckOutline | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM m2_outlines "
                "WHERE project_id = ? AND version = ?",
                (project_id, version),
            ).fetchone()
        return DeckOutline.model_validate_json(row[0]) if row else None

    def list_outlines(self, project_id: str) -> list[DeckOutline]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM m2_outlines WHERE project_id = ? "
                "ORDER BY version",
                (project_id,),
            ).fetchall()
        return [DeckOutline.model_validate_json(row[0]) for row in rows]

    def update_outline(self, current: DeckOutline, **changes) -> DeckOutline:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            superseded = current.model_copy(update={"status": "SUPERSEDED"})
            connection.execute(
                "UPDATE m2_outlines SET status = 'SUPERSEDED', "
                "payload = ? "
                "WHERE project_id = ? AND version = ?",
                (
                    superseded.model_dump_json(),
                    current.project_id,
                    current.version,
                ),
            )
            version = self._next_outline_version(connection, current.project_id)
            updated = current.model_copy(
                update={
                    **changes,
                    "version": version,
                    "parent_version": current.version,
                    "status": "DRAFT",
                }
            )
            self._insert_outline(connection, updated)
        return updated

    def approve_outline(self, project_id: str, version: int) -> DeckOutline:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM m2_outlines "
                "WHERE project_id = ? AND version = ? AND status = 'DRAFT'",
                (project_id, version),
            ).fetchone()
            if row is None:
                raise ValueError("outline is not an approvable draft")
            existing = connection.execute(
                "SELECT version, payload FROM m2_outlines "
                "WHERE project_id = ? AND status = 'APPROVED'",
                (project_id,),
            ).fetchall()
            for old_version, old_payload in existing:
                superseded = DeckOutline.model_validate_json(
                    old_payload
                ).model_copy(update={"status": "SUPERSEDED"})
                connection.execute(
                    "UPDATE m2_outlines SET status = ?, payload = ? "
                    "WHERE project_id = ? AND version = ?",
                    (
                        superseded.status,
                        superseded.model_dump_json(),
                        project_id,
                        old_version,
                    ),
                )
            approved = DeckOutline.model_validate_json(row[0]).model_copy(
                update={"status": "APPROVED"}
            )
            connection.execute(
                "UPDATE m2_outlines SET status = ?, payload = ? "
                "WHERE project_id = ? AND version = ?",
                (
                    approved.status,
                    approved.model_dump_json(),
                    project_id,
                    version,
                ),
            )
        return approved

    def restore_outline(self, project_id: str, version: int) -> DeckOutline:
        historical = self.get_outline(project_id, version)
        if historical is None:
            raise KeyError((project_id, version))
        return self.create_outline(
            historical.model_copy(
                update={"status": "DRAFT", "parent_version": version}
            )
        )

    def replace_research_tasks(
        self,
        project_id: str,
        outline_version: int,
        tasks: list[ResearchTask],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM m2_research_tasks "
                "WHERE project_id = ? AND outline_version = ?",
                (project_id, outline_version),
            )
            connection.executemany(
                "INSERT INTO m2_research_tasks VALUES (?, ?, ?, ?)",
                [
                    (
                        task.id,
                        project_id,
                        outline_version,
                        task.model_dump_json(),
                    )
                    for task in tasks
                ],
            )

    def list_research_tasks(
        self, project_id: str, outline_version: int
    ) -> list[ResearchTask]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM m2_research_tasks "
                "WHERE project_id = ? AND outline_version = ? ORDER BY id",
                (project_id, outline_version),
            ).fetchall()
        return [ResearchTask.model_validate_json(row[0]) for row in rows]
