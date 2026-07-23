from pathlib import Path

from pptmaker.powerpoint.client import _render_with_timeout_unlocked
from pptmaker.powerpoint.client import terminate_owned_powerpoint
from pptmaker.powerpoint.protocol import RenderRequest


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


def test_worker_process_forces_utf8_output(monkeypatch, tmp_path: Path):
    captured = {}

    class FakePopen:
        returncode = 0

        def __init__(self, *_args, **kwargs):
            captured.update(kwargs)

        def communicate(self, _input, timeout):
            return ('{"status":"success","elapsed_seconds":0}', "")

    monkeypatch.setattr("pptmaker.powerpoint.client.subprocess.Popen", FakePopen)
    request = RenderRequest(
        input_path=str(tmp_path / "input.pptx"),
        output_dir=str(tmp_path),
        run_id="utf8",
        idempotency_key="utf8",
        control_path=str(tmp_path / "control.json"),
        cancel_path=str(tmp_path / "cancel"),
    )

    assert _render_with_timeout_unlocked(request).status == "success"
    assert captured["env"]["PYTHONIOENCODING"] == "utf-8"
