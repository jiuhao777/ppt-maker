import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pptmaker.projects import ProjectCreate, ProjectRepository
from pptmaker.workflow import (
    build_foundation_graph,
    reconcile_interrupted_projects,
    run_foundation_step,
    sqlite_checkpointer,
)


def test_graph_resumes_checkpoint_after_reopen(tmp_path):
    path = tmp_path / "checkpoints.db"
    first = sqlite_checkpointer(path)
    run_foundation_step("project-1", first)
    first.conn.close()

    reopened = sqlite_checkpointer(path)
    state = build_foundation_graph(reopened).get_state(
        {"configurable": {"thread_id": "project-1"}}
    )
    reopened.conn.close()

    assert state.values["project_id"] == "project-1"
    assert state.values["completed_steps"] == ["foundation"]
    assert "api_key" not in state.values


def test_running_project_becomes_recoverable_after_process_death(tmp_path):
    database = tmp_path / "projects.db"
    root = Path(__file__).resolve().parents[2]
    environment = {
        **os.environ,
        "PYTHONPATH": str(root / "src"),
        "PYTHONIOENCODING": "utf-8",
    }
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("interrupted_worker.py")), str(database)],
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    project_id = process.stdout.readline().strip()
    assert project_id
    process.terminate()
    process.wait(timeout=5)

    repository = ProjectRepository(database)
    assert repository.get(project_id).execution_state == "RUNNING"
    assert reconcile_interrupted_projects(repository) == 1
    assert repository.get(project_id).execution_state == "FAILED_RECOVERABLE"


def test_recovery_keeps_running_project_with_active_lease(tmp_path):
    repository = ProjectRepository(tmp_path / "projects.db")
    active = repository.create(
        ProjectCreate(
            name="Active",
            execution_state="RUNNING",
            execution_lease_expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=5),
        )
    )

    assert reconcile_interrupted_projects(repository) == 0
    assert repository.get(active.id).execution_state == "RUNNING"
