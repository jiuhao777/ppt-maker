import sqlite3
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph


class FoundationState(TypedDict):
    project_id: str
    completed_steps: list[str]


def sqlite_checkpointer(path: Path) -> SqliteSaver:
    connection = sqlite3.connect(path, check_same_thread=False)
    return SqliteSaver(connection)


def build_foundation_graph(checkpointer: SqliteSaver):
    def complete_foundation(state: FoundationState) -> FoundationState:
        return {
            "project_id": state["project_id"],
            "completed_steps": [*state.get("completed_steps", []), "foundation"],
        }

    graph = StateGraph(FoundationState)
    graph.add_node("foundation", complete_foundation)
    graph.add_edge(START, "foundation")
    graph.add_edge("foundation", END)
    return graph.compile(checkpointer=checkpointer)


def run_foundation_step(project_id: str, checkpointer: SqliteSaver) -> dict:
    return build_foundation_graph(checkpointer).invoke(
        {"project_id": project_id, "completed_steps": []},
        {"configurable": {"thread_id": project_id}},
    )
