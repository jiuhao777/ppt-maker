import os
import subprocess
import sys
from pathlib import Path

from langgraph.types import Command

from pptmaker.m2.repository import M2Repository
from pptmaker.m2.workflow import (
    initial_state,
    build_m2_graph,
)
from pptmaker.projects import ProjectRepository
from pptmaker.workflow import reconcile_interrupted_projects
from pptmaker.workflow.foundation import sqlite_checkpointer


class FakeServices:
    def __init__(self, questions, api_key="TEST_KEY"):
        self.questions = list(questions)
        self.api_key = api_key
        self.answers = []
        self.research_tasks = 0

    def has_next_question(self, project_id):
        return self.questions.pop(0) if self.questions else False

    def accept_answer(self, project_id, answer):
        self.answers.append(answer)

    def generate_outline(self, project_id):
        return 1

    def approve_outline(self, project_id, version):
        self.research_tasks = 2
        return self.research_tasks


def config(project_id="p1"):
    return {"configurable": {"thread_id": project_id}}


def test_graph_pauses_after_one_question(tmp_path):
    graph = build_m2_graph(
        FakeServices([True]),
        sqlite_checkpointer(tmp_path / "checkpoints.db"),
    )

    graph.invoke(initial_state("p1"), config())
    state = graph.get_state(config()).values

    assert state["business_state"] == "WAITING_FOR_USER"
    assert state["question_count"] == 1


def test_answer_resumes_without_asking_known_question_again(tmp_path):
    services = FakeServices([True, False])
    graph = build_m2_graph(
        services,
        sqlite_checkpointer(tmp_path / "checkpoints.db"),
    )
    graph.invoke(initial_state("p1"), config())

    graph.invoke(Command(resume="Executives"), config())
    state = graph.get_state(config()).values

    assert services.answers == ["Executives"]
    assert state["business_state"] == "OUTLINE_REVIEW"
    assert state["question_count"] == 1


def test_checkpoint_contains_no_api_key(tmp_path):
    checkpoint_path = tmp_path / "checkpoints.db"
    graph = build_m2_graph(
        FakeServices([True]),
        sqlite_checkpointer(checkpoint_path),
    )

    graph.invoke(initial_state("p1"), config())

    assert "api_key" not in graph.get_state(config()).values
    assert b"TEST_KEY" not in checkpoint_path.read_bytes()


def test_unapproved_outline_cannot_create_research_tasks(tmp_path):
    services = FakeServices([False])
    graph = build_m2_graph(
        services,
        sqlite_checkpointer(tmp_path / "checkpoints.db"),
    )

    graph.invoke(initial_state("p1"), config())
    state = graph.get_state(config()).values

    assert state["business_state"] == "OUTLINE_REVIEW"
    assert state["research_task_count"] == 0


def test_explicit_approval_creates_research_tasks(tmp_path):
    services = FakeServices([False])
    graph = build_m2_graph(
        services,
        sqlite_checkpointer(tmp_path / "checkpoints.db"),
    )
    graph.invoke(initial_state("p1"), config())

    result = graph.invoke(Command(resume="approve"), config())

    assert result["business_state"] == "OUTLINE_APPROVED"
    assert result["research_task_count"] == 2


def test_interrupted_m2_project_keeps_context_and_becomes_recoverable(tmp_path):
    database = tmp_path / "pptmaker.db"
    root = Path(__file__).resolve().parents[2]
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).with_name("m2_interrupted_worker.py")),
            str(database),
        ],
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env={
            **os.environ,
            "PYTHONPATH": str(root / "src"),
            "PYTHONIOENCODING": "utf-8",
        },
    )
    project_id = process.stdout.readline().strip()
    assert project_id
    process.terminate()
    process.wait(timeout=5)

    projects = ProjectRepository(database)
    assert reconcile_interrupted_projects(projects) == 1
    assert projects.get(project_id).execution_state == "FAILED_RECOVERABLE"
    assert M2Repository(database).get_brief(project_id) is not None
