from typing import Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from pptmaker.m2.models import BusinessState


class M2GraphState(TypedDict):
    project_id: str
    business_state: BusinessState
    current_outline_version: int | None
    question_count: int
    research_task_count: int


class M2Services(Protocol):
    def has_next_question(self, project_id: str) -> bool: ...

    def accept_answer(self, project_id: str, answer: str) -> None: ...

    def generate_outline(self, project_id: str) -> int: ...

    def approve_outline(self, project_id: str, version: int) -> int: ...


def initial_state(project_id: str) -> M2GraphState:
    return {
        "project_id": project_id,
        "business_state": "COLLECTING_REQUIREMENTS",
        "current_outline_version": None,
        "question_count": 0,
        "research_task_count": 0,
    }


def build_m2_graph(services: M2Services, checkpointer):
    def advance(state: M2GraphState) -> dict:
        if services.has_next_question(state["project_id"]):
            return {
                "business_state": "WAITING_FOR_USER",
                "question_count": state["question_count"] + 1,
            }
        version = services.generate_outline(state["project_id"])
        return {
            "business_state": "OUTLINE_REVIEW",
            "current_outline_version": version,
        }

    def wait_for_answer(state: M2GraphState) -> dict:
        answer = interrupt({"kind": "requirement_answer"})
        services.accept_answer(state["project_id"], answer)
        return {"business_state": "COLLECTING_REQUIREMENTS"}

    def wait_for_approval(state: M2GraphState) -> dict:
        decision = interrupt(
            {
                "kind": "outline_approval",
                "version": state["current_outline_version"],
            }
        )
        if decision != "approve":
            return {"business_state": "OUTLINE_REVIEW"}
        count = services.approve_outline(
            state["project_id"],
            state["current_outline_version"],
        )
        return {
            "business_state": "OUTLINE_APPROVED",
            "research_task_count": count,
        }

    graph = StateGraph(M2GraphState)
    graph.add_node("advance", advance)
    graph.add_node("wait_for_answer", wait_for_answer)
    graph.add_node("wait_for_approval", wait_for_approval)
    graph.add_edge(START, "advance")
    graph.add_conditional_edges(
        "advance",
        lambda state: state["business_state"],
        {
            "WAITING_FOR_USER": "wait_for_answer",
            "OUTLINE_REVIEW": "wait_for_approval",
        },
    )
    graph.add_edge("wait_for_answer", "advance")
    graph.add_edge("wait_for_approval", END)
    return graph.compile(checkpointer=checkpointer)
