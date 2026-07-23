import json
import tempfile
from pathlib import Path

from pptmaker.projects import ProjectCreate, ProjectRepository, ProjectUpdate
from pptmaker.providers import OpenAICompatibleProvider, ProviderConfig
from pptmaker.workflow import (
    build_foundation_graph,
    reconcile_interrupted_projects,
    run_foundation_step,
    sqlite_checkpointer,
)


class _Completions:
    def create(self, **_kwargs):
        return object()


class _Client:
    chat = type("Chat", (), {"completions": _Completions()})()


def main() -> int:
    output = Path("artifacts/m1")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        checkpoint_path = root / "checkpoints.db"
        saver = sqlite_checkpointer(checkpoint_path)
        run_foundation_step("evidence-project", saver)
        saver.conn.close()
        reopened = sqlite_checkpointer(checkpoint_path)
        state = build_foundation_graph(reopened).get_state(
            {"configurable": {"thread_id": "evidence-project"}}
        )
        reopened.conn.close()

        repository = ProjectRepository(root / "projects.db")
        project = repository.create(ProjectCreate(name="Evidence"))
        repository.update(
            project.id,
            ProjectUpdate(execution_state="RUNNING"),
            expected_version=project.version,
        )
        reconcile_interrupted_projects(repository)
        recovered = repository.get(project.id)

        recovery_passed = (
            state.values.get("completed_steps") == ["foundation"]
            and "api_key" not in state.values
            and recovered.execution_state == "FAILED_RECOVERABLE"
        )
        (output / "restart-recovery.json").write_text(
            json.dumps(
                {
                    "status": "pass" if recovery_passed else "fail",
                    "checkpoint_restored": state.values.get("completed_steps")
                    == ["foundation"],
                    "interrupted_state": recovered.execution_state,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    config = ProviderConfig(
        provider_id="custom",
        base_url="https://test.invalid/v1",
        model="test-model",
    )
    report = OpenAICompatibleProvider(
        config, client_factory=lambda **_kwargs: _Client()
    ).probe("TEST_KEY")
    provider_passed = (
        report.status == "success"
        and report.capabilities["structured_output"].value is True
        and "TEST_KEY" not in report.model_dump_json()
    )
    (output / "provider-capabilities.json").write_text(
        json.dumps(
            {
                "status": "pass" if provider_passed else "fail",
                "capabilities": report.model_dump(mode="json")["capabilities"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0 if recovery_passed and provider_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
