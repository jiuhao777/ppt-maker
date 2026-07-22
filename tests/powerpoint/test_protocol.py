from pathlib import Path

import pytest
from pydantic import ValidationError

from pptmaker.powerpoint.protocol import RenderRequest


def _request(**overrides):
    root = Path("C:/m0").resolve()
    values = {
        "run_id": "r1",
        "idempotency_key": "k1",
        "input_path": str(root / "input.pptx"),
        "output_dir": str(root / "out"),
        "control_path": str(root / "control.json"),
        "cancel_path": str(root / "cancel.flag"),
    }
    values.update(overrides)
    return RenderRequest(**values)


@pytest.mark.parametrize(
    "field",
    ("input_path", "output_dir", "control_path", "cancel_path"),
)
def test_render_request_rejects_relative_paths(field: str):
    with pytest.raises(ValidationError, match="path must be absolute"):
        _request(**{field: "relative/path"})


def test_render_request_rejects_unsafe_run_id():
    with pytest.raises(ValidationError):
        _request(run_id="../escape")


def test_render_request_allows_hold_longer_than_timeout_for_fault_injection():
    request = _request(timeout_seconds=5, test_hold_seconds=15)
    assert request.test_hold_seconds > request.timeout_seconds
