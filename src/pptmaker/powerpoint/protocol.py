from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RenderRequest(BaseModel):
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    idempotency_key: str = Field(min_length=1, max_length=128)
    input_path: str
    output_dir: str
    control_path: str
    cancel_path: str
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    test_hold_seconds: int = Field(default=0, ge=0, le=30)

    @field_validator("input_path", "output_dir", "control_path", "cancel_path")
    @classmethod
    def absolute_paths_only(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("path must be absolute")
        return value

class RenderResponse(BaseModel):
    status: Literal["success", "failed"]
    owned_pid: int | None = None
    slide_images: list[str] = Field(default_factory=list)
    elapsed_seconds: float = Field(ge=0)
    error: str | None = None
    details: dict[str, str | bool] = Field(default_factory=dict)
