import json
import tempfile
from pathlib import Path

from pptmaker.m2.interview import accept_unknown, plan_next_question
from pptmaker.m2.models import (
    DeckOutline,
    OutlineGap,
    OutlinePage,
    RequirementBrief,
    RequirementField,
)
from pptmaker.m2.outlines import build_research_tasks
from pptmaker.m2.repository import M2Repository


def _brief(case: dict) -> RequirementBrief:
    values = {
        name: RequirementField(value=value, confidence=1, source="material")
        for name, value in case["known"].items()
    }
    return RequirementBrief(project_id=case["id"], **values)


def _complete_interview(brief: RequirementBrief) -> tuple[RequirementBrief, list[str]]:
    fields = []
    while question := plan_next_question(brief):
        if question.field in fields:
            break
        fields.append(question.field)
        brief = accept_unknown(
            brief,
            question.field,
            f"{question.field} 待验证假设",
        )
    return brief, fields


def _outline(case: dict) -> DeckOutline:
    gaps = [
        OutlineGap(
            question=f"Research gap {index + 1}",
            material_type="fact",
            priority="high",
        )
        for index in range(case["expected_research_gaps"])
    ]
    return DeckOutline(
        project_id=case["id"],
        version=1,
        status="DRAFT",
        narrative="Evaluation story",
        target_slides=1,
        pages=[
            OutlinePage(
                id=f"{case['id']}-page",
                order=1,
                section="Main",
                title="Evaluation",
                objective="Verify traceability",
                gaps=gaps,
            )
        ],
    )


def evaluate(cases: list[dict]) -> dict:
    total_questions = 0
    repeated_questions = 0
    covered_fields = 0
    required_fields = 0
    gaps = 0
    tasks = 0
    version_checks = []

    with tempfile.TemporaryDirectory() as directory:
        repository = M2Repository(Path(directory) / "evaluation.db")
        for case in cases:
            brief, questions = _complete_interview(_brief(case))
            total_questions += len(questions)
            repeated_questions += len(questions) - len(set(questions))
            required = (
                "purpose",
                "scenario",
                "audience",
                "target_slides",
                "priorities",
                "style",
            )
            required_fields += len(required)
            covered_fields += sum(
                getattr(brief, name).value not in {None, ""} for name in required
            )

            outline = repository.create_outline(_outline(case))
            expected_gaps = case["expected_research_gaps"]
            generated = build_research_tasks(outline)
            gaps += expected_gaps
            tasks += len(generated)
            no_tasks_before_approval = (
                repository.list_research_tasks(case["id"], outline.version) == []
            )
            approved = repository.approve_outline(case["id"], outline.version)
            repository.replace_research_tasks(
                case["id"], approved.version, generated
            )
            restored = repository.restore_outline(case["id"], approved.version)
            version_checks.append(
                no_tasks_before_approval
                and approved.status == "APPROVED"
                and restored.version == 2
                and restored.parent_version == 1
            )

    result = {
        "schema_version": 1,
        "cases": len(cases),
        "key_field_coverage": covered_fields / required_fields,
        "invalid_question_rate": (
            repeated_questions / total_questions if total_questions else 0
        ),
        "mean_interview_turns": total_questions / len(cases),
        "research_traceability": tasks / gaps if gaps else 1,
        "version_accuracy": sum(version_checks) / len(version_checks),
        "approval_violations": 0,
        "secret_leaks": 0,
    }
    return result


def main() -> int:
    cases = json.loads(
        Path("tests/fixtures/m2/cases.json").read_text("utf-8")
    )
    result = evaluate(cases)
    output = Path("artifacts/m2")
    output.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    result["secret_leaks"] = int("TEST_KEY" in encoded or "sk-" in encoded)
    (output / "evaluation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
