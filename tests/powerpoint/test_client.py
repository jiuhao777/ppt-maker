from pathlib import Path

from pptmaker.powerpoint.client import terminate_owned_powerpoint


class FakeProcess:
    def __init__(self, *, name: str, created: float):
        self._name = name
        self._created = created
        self.terminated = False

    def name(self) -> str:
        return self._name

    def create_time(self) -> float:
        return self._created

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float) -> None:
        return None


def test_cleanup_rejects_reused_pid_identity(tmp_path: Path):
    process = FakeProcess(name="POWERPNT.EXE", created=200.0)
    control = tmp_path / "control.json"
    control.write_text(
        '{"pid": 42, "run_id": "r1", "process_created_at": 100.0}',
        encoding="utf-8",
    )

    terminated = terminate_owned_powerpoint(
        control,
        expected_run_id="r1",
        process_factory=lambda _pid: process,
    )

    assert terminated is False
    assert process.terminated is False


def test_cleanup_terminates_only_matching_powerpoint(tmp_path: Path):
    process = FakeProcess(name="POWERPNT.EXE", created=100.0)
    control = tmp_path / "control.json"
    control.write_text(
        '{"pid": 42, "run_id": "r1", "process_created_at": 100.0}',
        encoding="utf-8",
    )

    terminated = terminate_owned_powerpoint(
        control,
        expected_run_id="r1",
        process_factory=lambda _pid: process,
    )

    assert terminated is True
    assert process.terminated is True
