import json
from pathlib import Path

from pptmaker.m0.powerpoint_probe import run_powerpoint_probe
from pptmaker.powerpoint.protocol import RenderResponse


def test_powerpoint_probe_combines_render_and_cleanup_evidence(tmp_path: Path):
    def fake_renderer(request):
        if request.run_id == "normal":
            return RenderResponse(
                status="success",
                owned_pid=123,
                slide_images=["slide-1.png", "slide-2.png"],
                elapsed_seconds=1.25,
            )
        Path(request.control_path).write_text(
            json.dumps(
                {
                    "pid": 99999999,
                    "run_id": request.run_id,
                    "process_created_at": 1.0,
                }
            ),
            encoding="utf-8",
        )
        return RenderResponse(
            status="failed",
            elapsed_seconds=5.0,
            error="worker hard timeout",
        )

    result = run_powerpoint_probe(
        tmp_path,
        renderer=fake_renderer,
        environment_reader=lambda: {"office_version": "test"},
    )

    assert result.status.value == "pass"
    assert result.metrics["rendered_slides"] == 2
    assert result.metrics["normal_process_stopped"] is True
    assert result.metrics["timeout_orphaned"] is False
    assert result.details["office_environment"]["office_version"] == "test"
