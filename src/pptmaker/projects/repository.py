import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pptmaker.projects.models import Project, ProjectCreate, ProjectUpdate


class VersionConflict(RuntimeError):
    pass


class ProjectRepository:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @staticmethod
    def _from_row(row) -> Project | None:
        if row is None:
            return None
        payload = json.loads(row[1])
        return Project(
            id=row[0],
            **payload,
            version=row[2],
            created_at=row[3],
            updated_at=row[4],
        )

    def create(self, values: ProjectCreate) -> Project:
        project_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        payload = values.model_dump()
        payload["schema_version"] = 1
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
                (project_id, json.dumps(payload), 1, now, now),
            )
        return self.get(project_id)

    def get(self, project_id: str) -> Project | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, payload, version, created_at, updated_at "
                "FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return self._from_row(row)

    def list(self) -> list[Project]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, payload, version, created_at, updated_at "
                "FROM projects ORDER BY created_at"
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def update(
        self,
        project_id: str,
        values: ProjectUpdate,
        expected_version: int,
    ) -> Project:
        current = self.get(project_id)
        if current is None:
            raise KeyError(project_id)
        payload = current.model_dump(
            exclude={"id", "version", "created_at", "updated_at"}
        )
        payload.update(values.model_dump(exclude_none=True))
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE projects SET payload = ?, version = version + 1, "
                "updated_at = ? WHERE id = ? AND version = ?",
                (json.dumps(payload), now, project_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise VersionConflict(project_id)
        return self.get(project_id)

    def delete(self, project_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    def mark_running_recoverable(self) -> int:
        updated = 0
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            rows = connection.execute("SELECT id, payload FROM projects").fetchall()
            for project_id, encoded in rows:
                payload = json.loads(encoded)
                if payload["execution_state"] != "RUNNING":
                    continue
                payload["execution_state"] = "FAILED_RECOVERABLE"
                connection.execute(
                    "UPDATE projects SET payload = ?, version = version + 1, "
                    "updated_at = ? WHERE id = ?",
                    (json.dumps(payload), now, project_id),
                )
                updated += 1
        return updated
