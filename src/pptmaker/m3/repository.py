import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pydantic import TypeAdapter

from pptmaker.m3.artifacts import GenerationArtifact
from pptmaker.m3.models import ContentPlan, DesignPlan, SlideSpec


class M3Repository:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS m3_content (project_id TEXT, outline_version INTEGER, payload TEXT NOT NULL, PRIMARY KEY (project_id, outline_version));
                CREATE TABLE IF NOT EXISTS m3_design (project_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS m3_specs (
                    project_id TEXT NOT NULL,
                    blueprint_version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (project_id, blueprint_version)
                );
                CREATE TABLE IF NOT EXISTS m3_artifacts (
                    project_id TEXT NOT NULL,
                    blueprint_version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (project_id, blueprint_version)
                );
            """)

    def _connect(self):
        return sqlite3.connect(self.path)

    def save_content(self, plan: ContentPlan):
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO m3_content VALUES (?, ?, ?)",
                         (plan.project_id, plan.outline_version, plan.model_dump_json()))

    def get_content(self, project_id: str, outline_version: int) -> ContentPlan | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM m3_content WHERE project_id=? AND outline_version=?",
                               (project_id, outline_version)).fetchone()
        return ContentPlan.model_validate_json(row[0]) if row else None

    def save_design(self, plan: DesignPlan):
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO m3_design VALUES (?, ?)",
                         (plan.project_id, plan.model_dump_json()))

    def get_design(self, project_id: str) -> DesignPlan | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM m3_design WHERE project_id=?",
                               (project_id,)).fetchone()
        return DesignPlan.model_validate_json(row[0]) if row else None

    def save_specs(
        self,
        project_id: str,
        blueprint_version: int,
        specs: list[SlideSpec],
    ) -> None:
        payload = TypeAdapter(list[SlideSpec]).dump_json(specs).decode()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO m3_specs VALUES (?, ?, ?)",
                (project_id, blueprint_version, payload),
            )

    def get_specs(
        self,
        project_id: str,
        blueprint_version: int,
    ) -> list[SlideSpec]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM m3_specs "
                "WHERE project_id = ? AND blueprint_version = ?",
                (project_id, blueprint_version),
            ).fetchone()
        return (
            TypeAdapter(list[SlideSpec]).validate_json(row[0])
            if row
            else []
        )

    def save_artifact(self, artifact: GenerationArtifact) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO m3_artifacts VALUES (?, ?, ?, ?)",
                (
                    artifact.project_id,
                    artifact.blueprint_version,
                    artifact.status,
                    artifact.model_dump_json(),
                ),
            )

    def get_artifact(
        self,
        project_id: str,
        blueprint_version: int,
    ) -> GenerationArtifact | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM m3_artifacts "
                "WHERE project_id = ? AND blueprint_version = ?",
                (project_id, blueprint_version),
            ).fetchone()
        return (
            GenerationArtifact.model_validate_json(row[0]) if row else None
        )

    def mark_running_recoverable(
        self,
        project_id: str | None = None,
    ) -> int:
        with self._connect() as conn:
            query = (
                "SELECT project_id, blueprint_version, payload "
                "FROM m3_artifacts WHERE status = 'RUNNING'"
            )
            params: tuple[str, ...] = ()
            if project_id is not None:
                query += " AND project_id = ?"
                params = (project_id,)
            rows = conn.execute(query, params).fetchall()
            for item_project_id, version, payload in rows:
                artifact = GenerationArtifact.model_validate_json(
                    payload
                ).model_copy(
                    update={
                        "status": "FAILED_RECOVERABLE",
                        "safe_error_type": "interrupted",
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
                conn.execute(
                    "UPDATE m3_artifacts SET status = ?, payload = ? "
                    "WHERE project_id = ? AND blueprint_version = ?",
                    (
                        artifact.status,
                        artifact.model_dump_json(),
                        item_project_id,
                        version,
                    ),
                )
        return len(rows)
