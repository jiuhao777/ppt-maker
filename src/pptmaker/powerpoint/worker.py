import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

import psutil
import pythoncom
import win32com.client

from pptmaker.powerpoint.preflight import preflight_issues
from pptmaker.powerpoint.protocol import RenderRequest, RenderResponse


def _write_control(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(temporary, path)


def _heartbeat(
    path: Path,
    identity: dict,
    stop: threading.Event,
) -> None:
    while not stop.wait(1.0):
        _write_control(path, {**identity, "heartbeat": time.time()})


def _slide_number(path: Path) -> int:
    match = re.search(r"(\d+)(?!.*\d)", path.stem)
    return int(match.group(1)) if match else 0


class ExportPublisher:
    def __init__(self, output_dir: Path, run_id: str):
        self.final = output_dir / run_id
        # PowerPoint treats a dot in the final path component as a file
        # extension and may silently export to the stem instead.
        self.temporary = output_dir / f"_{run_id}_partial_{uuid4().hex}"

    def publish(self, expected_count: int) -> list[Path]:
        images = sorted(self.temporary.glob("*.PNG"), key=_slide_number)
        numbers = [_slide_number(path) for path in images]
        if numbers != list(range(1, expected_count + 1)):
            raise RuntimeError(
                f"PowerPoint slide export mismatch: expected {expected_count}, got {numbers}"
            )
        if any(not path.is_file() for path in images):
            raise RuntimeError("PowerPoint export contains a non-file entry")
        if self.final.exists():
            raise RuntimeError("final PowerPoint render output already exists")
        os.replace(self.temporary, self.final)
        return [self.final / path.name for path in images]


def _powerpoint_pids() -> set[int]:
    return {
        process.pid
        for process in psutil.process_iter(["name"])
        if (process.info["name"] or "").lower() == "powerpnt.exe"
    }


def _wait_for_single_new_powerpoint(previous: set[int], timeout: float = 5) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        created = _powerpoint_pids() - previous
        if len(created) == 1:
            return created.pop()
        if len(created) > 1:
            raise RuntimeError(f"PowerPoint created multiple candidate processes: {sorted(created)}")
        time.sleep(0.1)
    raise RuntimeError("PowerPoint process did not appear after DispatchEx")


def ensure_owned_process_stopped(
    pid: int | None,
    created_at: float | None,
    process_factory=psutil.Process,
) -> bool:
    if pid is None or created_at is None:
        return True
    try:
        process = process_factory(pid)
        if (process.name() or "").lower() != "powerpnt.exe":
            return False
        if abs(process.create_time() - created_at) > 0.01:
            return False
        try:
            process.wait(timeout=3)
            return True
        except psutil.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=3)
            except psutil.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            return True
    except psutil.NoSuchProcess:
        return True


def render(request: RenderRequest) -> RenderResponse:
    started = time.perf_counter()
    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
    app = None
    presentation = None
    owned_pid = None
    owned_created_at = None
    heartbeat_stop = threading.Event()
    heartbeat_thread = None
    try:
        issues = preflight_issues(Path(request.input_path))
        if issues:
            raise RuntimeError("PowerPoint preflight failed: " + ",".join(issues))
        if Path(request.cancel_path).exists():
            raise RuntimeError("task cancelled before PowerPoint launch")

        publisher = ExportPublisher(Path(request.output_dir), request.run_id)
        publisher.temporary.parent.mkdir(parents=True, exist_ok=True)
        publisher.temporary.mkdir(parents=True, exist_ok=False)
        previous_powerpoint_pids = _powerpoint_pids()
        app = win32com.client.DispatchEx("PowerPoint.Application")
        owned_pid = _wait_for_single_new_powerpoint(previous_powerpoint_pids)
        owned_created_at = psutil.Process(owned_pid).create_time()
        identity = {
            "pid": owned_pid,
            "run_id": request.run_id,
            "process_created_at": owned_created_at,
            "heartbeat": time.time(),
        }
        control = Path(request.control_path)
        _write_control(control, identity)
        heartbeat_thread = threading.Thread(
            target=_heartbeat,
            args=(control, identity, heartbeat_stop),
            daemon=True,
        )
        heartbeat_thread.start()

        if Path(request.cancel_path).exists():
            raise RuntimeError("task cancelled before PowerPoint open")
        if request.test_hold_seconds:
            time.sleep(request.test_hold_seconds)
        if Path(request.cancel_path).exists():
            raise RuntimeError("task cancelled before PowerPoint open")

        app.Visible = True
        app.DisplayAlerts = 1
        presentation = app.Presentations.Open(
            request.input_path,
            ReadOnly=True,
            Untitled=False,
            WithWindow=False,
        )
        presentation.Export(str(publisher.temporary), "PNG")
        if Path(request.cancel_path).exists():
            raise RuntimeError("task cancelled after PowerPoint export")

        images = publisher.publish(int(presentation.Slides.Count))
        return RenderResponse(
            status="success",
            owned_pid=owned_pid,
            slide_images=[str(path.resolve()) for path in images],
            elapsed_seconds=time.perf_counter() - started,
        )
    except Exception as exc:
        return RenderResponse(
            status="failed",
            owned_pid=owned_pid,
            error=f"{type(exc).__name__}: {exc}",
            elapsed_seconds=time.perf_counter() - started,
        )
    finally:
        heartbeat_stop.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=2)
        try:
            if presentation is not None:
                presentation.Close()
        except Exception:
            pass
        try:
            if app is not None:
                app.Quit()
        except Exception:
            pass
        ensure_owned_process_stopped(owned_pid, owned_created_at)
        pythoncom.CoUninitialize()


def main() -> int:
    try:
        request = RenderRequest.model_validate_json(sys.stdin.read())
        response = render(request)
        sys.stdout.write(response.model_dump_json())
        return 0
    except Exception as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
