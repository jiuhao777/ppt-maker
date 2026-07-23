from pathlib import Path

import pytest

from pptmaker.m0.pptx_probe import build_baseline_deck
from pptmaker.powerpoint.idempotency import (
    IdempotencyConflict,
    IdempotencyJournal,
    request_fingerprint,
)
from pptmaker.powerpoint.protocol import RenderRequest, RenderResponse
from pptmaker.powerpoint.worker import ExportPublisher, ensure_owned_process_stopped


def _request(tmp_path: Path, key: str = "key") -> RenderRequest:
    deck = (tmp_path / "deck.pptx").resolve()
    build_baseline_deck(deck)
    return RenderRequest(
        run_id="run",
        idempotency_key=key,
        input_path=str(deck),
        output_dir=str((tmp_path / "output").resolve()),
        control_path=str((tmp_path / "control.json").resolve()),
        cancel_path=str((tmp_path / "cancel.flag").resolve()),
    )


def test_completed_request_replays_without_launch(tmp_path: Path):
    request = _request(tmp_path)
    fingerprint = request_fingerprint(request)
    slide = tmp_path / "slide1.PNG"
    slide.write_bytes(b"png")
    response = RenderResponse(
        status="success",
        slide_images=[str(slide)],
        elapsed_seconds=1,
    )
    journal = IdempotencyJournal(tmp_path / "journal")
    journal.complete("key", fingerprint, response)

    replay = journal.lookup("key", fingerprint)

    assert replay.status == "success"
    assert replay.details["idempotent_replay"] is True


def test_same_key_with_different_fingerprint_is_rejected(tmp_path: Path):
    journal = IdempotencyJournal(tmp_path / "journal")
    journal.claim("key", "first")
    with pytest.raises(IdempotencyConflict):
        journal.lookup("key", "second")


def test_partial_export_is_not_visible_as_final(tmp_path: Path):
    publisher = ExportPublisher(tmp_path, "run")
    publisher.temporary.mkdir(parents=True)
    (publisher.temporary / "幻灯片1.PNG").write_bytes(b"png")
    assert not publisher.final.exists()
    images = publisher.publish(1)
    assert publisher.final.is_dir()
    assert images == [publisher.final / "幻灯片1.PNG"]


def test_worker_force_stops_owned_powerpoint_when_quit_does_not():
    class Process:
        terminated = False

        def name(self):
            return "POWERPNT.EXE"

        def create_time(self):
            return 12.5

        def wait(self, timeout):
            if not self.terminated:
                import psutil

                raise psutil.TimeoutExpired(timeout)

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.terminated = True

    process = Process()
    assert ensure_owned_process_stopped(
        42, 12.5, process_factory=lambda _pid: process
    )
    assert process.terminated
