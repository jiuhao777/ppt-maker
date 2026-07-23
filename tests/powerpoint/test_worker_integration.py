import json
import re
import threading
import time
from pathlib import Path

import psutil
import pytest

from pptmaker.m0.pptx_probe import build_baseline_deck
from pptmaker.powerpoint.client import render_with_timeout
from pptmaker.powerpoint.protocol import RenderRequest


def _powerpoint_pids() -> set[int]:
    return {
        process.pid
        for process in psutil.process_iter(["name"])
        if (process.info["name"] or "").lower() == "powerpnt.exe"
    }


def _request(tmp_path: Path, run_id: str, **overrides) -> RenderRequest:
    deck = (tmp_path / "baseline.pptx").resolve()
    if not deck.exists():
        build_baseline_deck(deck)
    values = {
        "run_id": run_id,
        "idempotency_key": f"{run_id}-v1",
        "input_path": str(deck),
        "output_dir": str((tmp_path / "renders").resolve()),
        "control_path": str((tmp_path / f"{run_id}-control.json").resolve()),
        "cancel_path": str((tmp_path / f"{run_id}-cancel.flag").resolve()),
        "timeout_seconds": 60,
    }
    values.update(overrides)
    return RenderRequest(**values)


def _wait_for_control(path: Path, timeout: float = 10) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return json.loads(path.read_text("utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            time.sleep(0.1)
    raise AssertionError(f"control channel was not created: {path}")


@pytest.fixture(autouse=True)
def require_clean_powerpoint_environment():
    existing = _powerpoint_pids()
    if existing:
        pytest.skip(f"formal M0 test requires PowerPoint to be closed: {sorted(existing)}")
    yield
    deadline = time.monotonic() + 10
    while _powerpoint_pids() and time.monotonic() < deadline:
        time.sleep(0.2)
    assert _powerpoint_pids() == set()


@pytest.mark.office
def test_powerpoint_exports_each_slide_in_numeric_order(tmp_path: Path):
    response = render_with_timeout(_request(tmp_path, "office-probe"))

    assert response.status == "success", response.error
    page_numbers = [int(re.search(r"\d+", Path(path).stem).group()) for path in response.slide_images]
    assert page_numbers == [1, 2]
    assert response.owned_pid is not None


@pytest.mark.office
def test_timeout_leaves_no_owned_powerpoint_process(tmp_path: Path):
    request = _request(
        tmp_path,
        "timeout-probe",
        timeout_seconds=5,
        test_hold_seconds=15,
    )

    response = render_with_timeout(request)

    assert response.status == "failed"
    assert response.error == "worker hard timeout"
    control = json.loads(Path(request.control_path).read_text("utf-8"))
    assert not psutil.pid_exists(int(control["pid"]))


@pytest.mark.office
def test_prelaunch_cancellation_starts_no_powerpoint(tmp_path: Path):
    request = _request(tmp_path, "cancel-probe")
    Path(request.cancel_path).touch()

    response = render_with_timeout(request)

    assert response.status == "failed"
    assert "cancelled" in (response.error or "")
    assert response.owned_pid is None
    assert not Path(request.control_path).exists()


@pytest.mark.office
def test_control_channel_heartbeat_advances(tmp_path: Path):
    request = _request(
        tmp_path,
        "heartbeat-probe",
        timeout_seconds=15,
        test_hold_seconds=5,
    )
    result = {}
    thread = threading.Thread(
        target=lambda: result.setdefault("response", render_with_timeout(request)),
        daemon=True,
    )
    thread.start()
    first = _wait_for_control(Path(request.control_path))
    time.sleep(1.5)
    second = _wait_for_control(Path(request.control_path))
    thread.join(timeout=20)

    assert second["heartbeat"] > first["heartbeat"]
    assert result["response"].status == "success", result["response"].error


@pytest.mark.office
def test_completed_request_replays_without_launching_powerpoint(tmp_path: Path):
    request = _request(tmp_path, "replay-probe")
    first = render_with_timeout(request)
    assert first.status == "success", first.error
    assert _powerpoint_pids() == set()

    second = render_with_timeout(request)

    assert second.status == "success"
    assert second.slide_images == first.slide_images
    assert second.details["idempotent_replay"] is True
    assert _powerpoint_pids() == set()
