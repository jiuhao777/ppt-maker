from pathlib import Path
from uuid import uuid4

from pptmaker.powerpoint.client import render_with_timeout
from pptmaker.powerpoint.protocol import RenderRequest


class RenderError(RuntimeError):
    pass


def render_pptx(input_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    request = RenderRequest(
        run_id=f"m3-{uuid4().hex[:12]}",
        idempotency_key=f"render-{input_path.stem}",
        input_path=str(input_path.resolve()),
        output_dir=str(output_dir.resolve()),
        control_path=str(output_dir.resolve() / "control.json"),
        cancel_path=str(output_dir.resolve() / "cancel.txt"),
    )
    response = render_with_timeout(request)
    if response.status != "success":
        raise RenderError(response.error or "render failed")
    return [Path(p) for p in response.slide_images]
