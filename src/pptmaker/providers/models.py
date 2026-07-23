from typing import Literal

from pydantic import BaseModel, Field

from pptmaker.security.secrets import ProviderError


class ProviderConfig(BaseModel):
    provider_id: str
    base_url: str
    model: str


class Capability(BaseModel):
    value: bool | int | Literal["unknown"]
    source: Literal["probed", "preset", "unknown"]


class CapabilityReport(BaseModel):
    status: Literal["success", "failed"]
    capabilities: dict[str, Capability] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: ProviderError | None = None
