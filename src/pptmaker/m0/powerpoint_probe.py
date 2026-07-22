import json
import time
from collections.abc import Callable
from pathlib import Path

import psutil

from pptmaker.m0.contracts import ProbeResult, ProbeStatus
from pptmaker.m0.pptx_probe import build_baseline_deck
from pptmaker.powerpoint.client import render_with_timeout
from pptmaker.powerpoint.preflight import office_environment
from pptmaker.powerpoint.protocol import RenderRequest, RenderResponse


Renderer = Callable[[RenderRequest], RenderResponse]
EnvironmentReader = Callable[[], dict]


def _wait_for_process_exit(pid: int | None, timeout: float = 10) -> bool:
    if pid is None:
        return True
    deadline = time.monotonic() + timeout
    while psutil.pid_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    return not psutil.pid_exists(pid)


def run_powerpoint_probe(
    root: Path,
    renderer: Renderer = render_with_timeout,
    environment_reader: EnvironmentReader = office_environment,
) -> ProbeResult:
    run_stamp = str(time.time_ns())
    work = (root / "artifacts" / "m0" / "powerpoint-probe" / run_stamp).resolve()
    work.mkdir(parents=True, exist_ok=False)
    deck = (work / "baseline.pptx").resolve()
    build_baseline_deck(deck)

    normal = renderer(
        RenderRequest(
            run_id="normal",
            idempotency_key=f"normal-{run_stamp}",
            input_path=str(deck),
            output_dir=str(work),
            control_path=str(work / "normal-control.json"),
            cancel_path=str(work / "normal-cancel.flag"),
            timeout_seconds=60,
        )
    )
    normal_stopped = _wait_for_process_exit(normal.owned_pid)

    timeout_control = work / "timeout-control.json"
    timed = renderer(
        RenderRequest(
            run_id="timeout",
            idempotency_key=f"timeout-{run_stamp}",
            input_path=str(deck),
            output_dir=str(work),
            control_path=str(timeout_control),
            cancel_path=str(work / "timeout-cancel.flag"),
            timeout_seconds=5,
            test_hold_seconds=15,
        )
    )

    timeout_identity = (
        json.loads(timeout_control.read_text("utf-8"))
        if timeout_control.exists()
        else None
    )
    owned_pid = int(timeout_identity["pid"]) if timeout_identity else None
    orphaned = psutil.pid_exists(owned_pid) if owned_pid is not None else False
    passed = (
        normal.status == "success"
        and len(normal.slide_images) == 2
        and normal_stopped
        and timed.status == "failed"
        and timed.error == "worker hard timeout"
        and timeout_identity is not None
        and not orphaned
    )
    return ProbeResult(
        name="powerpoint-worker",
        status=ProbeStatus.PASS if passed else ProbeStatus.FAIL,
        metrics={
            "rendered_slides": len(normal.slide_images),
            "normal_elapsed_seconds": normal.elapsed_seconds,
            "normal_process_stopped": normal_stopped,
            "timeout_elapsed_seconds": timed.elapsed_seconds,
            "timeout_orphaned": orphaned,
        },
        limitations=[
            "Formal M0 support requires no pre-existing PowerPoint instance.",
            "Protected View recovery and final PPTX atomic replacement are deferred.",
        ],
        evidence=normal.slide_images,
        details={
            "normal_response": normal.model_dump(mode="json"),
            "timeout_response": timed.model_dump(mode="json"),
            "timeout_identity": timeout_identity,
            "office_environment": environment_reader(),
        },
    )
