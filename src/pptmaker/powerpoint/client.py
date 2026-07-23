import json
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import psutil

from pptmaker.powerpoint.protocol import RenderRequest, RenderResponse
from pptmaker.powerpoint.idempotency import (
    IdempotencyConflict,
    IdempotencyJournal,
    request_fingerprint,
)


class ManagedProcess(Protocol):
    def name(self) -> str: ...
    def create_time(self) -> float: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float) -> None: ...


ProcessFactory = Callable[[int], ManagedProcess]
_RENDER_LOCK = threading.Lock()


def terminate_owned_powerpoint(
    control_path: Path,
    expected_run_id: str,
    process_factory: ProcessFactory = psutil.Process,
) -> bool:
    try:
        identity = json.loads(control_path.read_text("utf-8"))
        if identity.get("run_id") != expected_run_id:
            return False
        process = process_factory(int(identity["pid"]))
        if process.name().lower() != "powerpnt.exe":
            return False
        if abs(process.create_time() - float(identity["process_created_at"])) > 0.01:
            return False
        process.terminate()
        try:
            process.wait(timeout=5)
        except psutil.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        return True
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, psutil.NoSuchProcess):
        return False


def _render_with_timeout_unlocked(request: RenderRequest) -> RenderResponse:
    started = time.perf_counter()
    process = subprocess.Popen(
        [sys.executable, "-m", "pptmaker.powerpoint.worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        stdout, stderr = process.communicate(
            request.model_dump_json(),
            timeout=request.timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        terminate_owned_powerpoint(Path(request.control_path), request.run_id)
        return RenderResponse(
            status="failed",
            elapsed_seconds=time.perf_counter() - started,
            error="worker hard timeout",
            details={"cleanup_attempted": True},
        )
    if process.returncode != 0:
        response = RenderResponse(
            status="failed",
            elapsed_seconds=time.perf_counter() - started,
            error=stderr.strip() or "worker failed",
        )
        cleaned = terminate_owned_powerpoint(
            Path(request.control_path), request.run_id
        )
        return response.model_copy(
            update={"details": {"cleanup_attempted": True, "cleanup_succeeded": cleaned}}
        )
    try:
        response = RenderResponse.model_validate_json(stdout)
        if response.status == "failed":
            cleaned = terminate_owned_powerpoint(
                Path(request.control_path), request.run_id
            )
            response = response.model_copy(
                update={
                    "details": {
                        **response.details,
                        "cleanup_attempted": True,
                        "cleanup_succeeded": cleaned,
                    }
                }
            )
        return response
    except Exception as exc:
        response = RenderResponse(
            status="failed",
            elapsed_seconds=time.perf_counter() - started,
            error=f"invalid worker response: {type(exc).__name__}: {exc}",
        )
        cleaned = terminate_owned_powerpoint(
            Path(request.control_path), request.run_id
        )
        return response.model_copy(
            update={"details": {"cleanup_attempted": True, "cleanup_succeeded": cleaned}}
        )


def render_with_timeout(request: RenderRequest) -> RenderResponse:
    with _RENDER_LOCK:
        journal = IdempotencyJournal(
            Path(request.output_dir) / ".idempotency"
        )
        fingerprint = request_fingerprint(request)
        try:
            replay = journal.lookup(request.idempotency_key, fingerprint)
            if replay is not None:
                return replay
            journal.claim(request.idempotency_key, fingerprint)
        except IdempotencyConflict as exc:
            return RenderResponse(
                status="failed",
                elapsed_seconds=0,
                error=f"IdempotencyConflict: {exc}",
            )
        response = _render_with_timeout_unlocked(request)
        if response.status == "success":
            journal.complete(request.idempotency_key, fingerprint, response)
        else:
            journal.fail(
                request.idempotency_key,
                fingerprint,
                response.error or "worker failed",
            )
        return response
