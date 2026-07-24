import sqlite3
from pathlib import Path

from pptmaker.m3.models import ContentPlan, DesignPlan


class M3Repository:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS m3_content (project_id TEXT, outline_version INTEGER, payload TEXT NOT NULL, PRIMARY KEY (project_id, outline_version));
                CREATE TABLE IF NOT EXISTS m3_design (project_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
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
