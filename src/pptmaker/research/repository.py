import sqlite3
from pathlib import Path

from pptmaker.research.contracts import FactRecord, ResearchRun


class ResearchRepository:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS research_facts (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def replace_facts(
        self,
        project_id: str,
        facts: list[FactRecord],
    ) -> None:
        if any(item.project_id != project_id for item in facts):
            raise ValueError("fact project does not match")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM research_facts WHERE project_id = ?",
                (project_id,),
            )
            connection.executemany(
                "INSERT INTO research_facts VALUES (?, ?, ?)",
                [
                    (item.id, project_id, item.model_dump_json())
                    for item in facts
                ],
            )

    def list_facts(
        self,
        project_id: str,
        *,
        active_only: bool = False,
    ) -> list[FactRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM research_facts "
                "WHERE project_id = ? ORDER BY rowid",
                (project_id,),
            ).fetchall()
        facts = [FactRecord.model_validate_json(row[0]) for row in rows]
        return (
            [item for item in facts if not item.excluded]
            if active_only
            else facts
        )

    def exclude_fact(self, project_id: str, fact_id: str) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM research_facts "
                "WHERE project_id = ? AND id = ?",
                (project_id, fact_id),
            ).fetchone()
            if row is None:
                raise KeyError(fact_id)
            fact = FactRecord.model_validate_json(row[0]).model_copy(
                update={"excluded": True}
            )
            connection.execute(
                "UPDATE research_facts SET payload = ? "
                "WHERE project_id = ? AND id = ?",
                (fact.model_dump_json(), project_id, fact_id),
            )

    def save_run(self, run: ResearchRun) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO research_runs (project_id, payload) VALUES (?, ?)",
                (run.project_id, run.model_dump_json()),
            )

    def get_latest_run(self, project_id: str) -> ResearchRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM research_runs WHERE project_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return ResearchRun.model_validate_json(row[0]) if row else None
