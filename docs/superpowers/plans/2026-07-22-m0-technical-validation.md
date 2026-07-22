# M0 Technical Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce reproducible evidence for the highest-risk PPT-maker decisions before building the product workflow.

**Architecture:** Build small probes behind stable contracts, not production subsystems. Each probe writes machine-readable results under `artifacts/m0/`; the final gate converts those results into ADRs and a go/no-go report.

**Tech Stack:** Conda `AI`, Python 3.10.20, pytest, Pydantic 2.13.4, python-pptx, pywin32, OpenAI SDK 2.45.0, httpx 0.28.1, Pillow 12.3.0, Torch 2.6.0+cu124, Transformers 4.56.0, Microsoft PowerPoint.

## Global Constraints

- Execute Python as `conda run -n AI python ...` and tests as `conda run -n AI python -m pytest ...`.
- Use only synthetic content or license-recorded public fixtures.
- Never commit API keys, downloaded model weights, generated output, temporary Office files, or public assets.
- A probe failure is a valid M0 result; do not hide it with fallback behavior.
- PowerPoint automation must run in STA and may terminate only the exact PID it owns.
- Network tests must reject loopback, private, link-local, reserved, and cloud metadata targets.
- Commit after every task that passes its own gate.

---

### Task 1: Repository and M0 Test Foundation

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `src/pptmaker/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_environment.py`

**Interfaces:**
- Consumes: Conda environment `AI` with Python 3.10.20.
- Produces: installable `pptmaker` package and `m0` pytest marker.

- [ ] **Step 1: Write the environment test**

```python
# tests/test_environment.py
import platform
import sys


def test_supported_runtime():
    assert sys.version_info[:3] == (3, 10, 20)
    assert platform.system() == "Windows"
```

- [ ] **Step 2: Add pytest marker registration**

```python
# tests/conftest.py
def pytest_configure(config):
    config.addinivalue_line("markers", "m0: M0 technical validation")
    config.addinivalue_line("markers", "office: requires Microsoft PowerPoint")
    config.addinivalue_line("markers", "online: requires an explicitly configured API key")
```

- [ ] **Step 3: Add packaging and test configuration**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling==1.28.0"]
build-backend = "hatchling.build"

[project]
name = "ppt-maker"
version = "0.1.0"
requires-python = "==3.10.20"
dependencies = [
  "pydantic==2.13.4",
  "python-pptx==1.0.2",
  "pywin32==311; sys_platform == 'win32'",
  "Pillow==12.3.0",
  "httpx==0.28.1",
  "openai==2.45.0",
]

[project.optional-dependencies]
test = ["pytest==9.0.2", "pytest-cov==7.0.0"]

[tool.hatch.build.targets.wheel]
packages = ["src/pptmaker"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

- [ ] **Step 4: Protect local and generated data**

```gitignore
# .gitignore
models/
projects/
artifacts/
.env
.env.*
!.env.example
*.key
*.pptx
*.pdf
*.docx
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
node_modules/
dist/
build/
```

- [ ] **Step 5: Install the project and run the test**

Run:

```powershell
conda run -n AI python -m pip install -e ".[test]"
conda run -n AI python -m pytest tests/test_environment.py -v
```

Expected: one passing test and no unknown-marker warning.

- [ ] **Step 6: Commit**

```powershell
git add .gitignore pyproject.toml src/pptmaker/__init__.py tests/conftest.py tests/test_environment.py
git commit -m "chore: establish M0 test foundation"
```

### Task 2: Artifact and Probe Result Contracts

**Files:**
- Create: `src/pptmaker/m0/contracts.py`
- Create: `src/pptmaker/m0/artifacts.py`
- Test: `tests/m0/test_artifacts.py`

**Interfaces:**
- Consumes: a repository root and probe name.
- Produces: `ProbeResult` and `write_probe_result(result, root) -> Path`.

- [ ] **Step 1: Write failing serialization tests**

```python
# tests/m0/test_artifacts.py
import json
from pathlib import Path

from pptmaker.m0.artifacts import write_probe_result
from pptmaker.m0.contracts import ProbeResult, ProbeStatus


def test_probe_result_is_written_under_artifacts(tmp_path: Path):
    result = ProbeResult(name="pptx-baseline", status=ProbeStatus.PASS, metrics={"slides": 2})
    path = write_probe_result(result, tmp_path)
    assert path == tmp_path / "artifacts" / "m0" / "pptx-baseline.json"
    assert json.loads(path.read_text("utf-8"))["metrics"]["slides"] == 2
```

- [ ] **Step 2: Verify the test fails**

Run: `conda run -n AI python -m pytest tests/m0/test_artifacts.py -v`  
Expected: FAIL because `pptmaker.m0` does not exist.

- [ ] **Step 3: Implement contracts and atomic JSON writing**

```python
# src/pptmaker/m0/contracts.py
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProbeStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


class ProbeResult(BaseModel):
    name: str
    status: ProbeStatus
    metrics: dict[str, float | int | str | bool] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
```

```python
# src/pptmaker/m0/artifacts.py
import os
from pathlib import Path

from pptmaker.m0.contracts import ProbeResult


def write_probe_result(result: ProbeResult, root: Path) -> Path:
    target = root / "artifacts" / "m0" / f"{result.name}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    os.replace(temporary, target)
    return target
```

- [ ] **Step 4: Run tests**

Run: `conda run -n AI python -m pytest tests/m0/test_artifacts.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/m0 tests/m0/test_artifacts.py
git commit -m "feat: add M0 probe result contracts"
```

### Task 3: Editable PPTX Baseline

**Files:**
- Create: `src/pptmaker/m0/pptx_probe.py`
- Test: `tests/m0/test_pptx_probe.py`

**Interfaces:**
- Consumes: `build_baseline_deck(output: Path) -> ProbeResult`.
- Produces: a two-slide editable PPTX with text, shape, table, image, and native chart.

- [ ] **Step 1: Write the package-level test**

```python
# tests/m0/test_pptx_probe.py
from pathlib import Path
from zipfile import ZipFile

from pptmaker.m0.pptx_probe import build_baseline_deck


def test_baseline_deck_contains_two_slides_and_chart(tmp_path: Path):
    output = tmp_path / "baseline.pptx"
    result = build_baseline_deck(output)
    assert result.status.value == "pass"
    with ZipFile(output) as package:
        names = set(package.namelist())
    assert "ppt/slides/slide1.xml" in names
    assert "ppt/slides/slide2.xml" in names
    assert any(name.startswith("ppt/charts/chart") for name in names)
```

- [ ] **Step 2: Verify failure**

Run: `conda run -n AI python -m pytest tests/m0/test_pptx_probe.py -v`  
Expected: FAIL because `build_baseline_deck` is missing.

- [ ] **Step 3: Implement the editable deck**

```python
# src/pptmaker/m0/pptx_probe.py
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import ChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches, Pt

from pptmaker.m0.contracts import ProbeResult, ProbeStatus


def build_baseline_deck(output: Path) -> ProbeResult:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    title_slide = prs.slides.add_slide(prs.slide_layouts[6])
    title = title_slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11.7), Inches(1.0))
    run = title.text_frame.paragraphs[0].add_run()
    run.text, run.font.size, run.font.bold = "PPT-maker 技术验证", Pt(30), True
    card = title_slide.shapes.add_shape(1, Inches(0.8), Inches(2.0), Inches(4.0), Inches(2.0))
    card.fill.solid()
    card.fill.fore_color.rgb = RGBColor(31, 78, 121)
    card.text = "文本与形状保持可编辑"

    data_slide = prs.slides.add_slide(prs.slide_layouts[6])
    table = data_slide.shapes.add_table(3, 2, Inches(0.7), Inches(0.8), Inches(4.2), Inches(2.2)).table
    for row, values in enumerate((("阶段", "得分"), ("生成", "80"), ("修复", "92"))):
        for col, value in enumerate(values):
            table.cell(row, col).text = value
    chart_data = ChartData()
    chart_data.categories = ["生成", "修复"]
    chart_data.add_series("质量", (80, 92))
    data_slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(5.3), Inches(0.8), Inches(7.2), Inches(4.8), chart_data
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    prs.save(output)
    return ProbeResult(name="pptx-baseline", status=ProbeStatus.PASS, metrics={"slides": 2})
```

- [ ] **Step 4: Run test and create evidence**

Run:

```powershell
conda run -n AI python -m pytest tests/m0/test_pptx_probe.py -v
conda run -n AI python -c "from pathlib import Path; from pptmaker.m0.pptx_probe import build_baseline_deck; build_baseline_deck(Path('artifacts/m0/baseline.pptx'))"
```

Expected: PASS and `artifacts/m0/baseline.pptx` exists.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/m0/pptx_probe.py tests/m0/test_pptx_probe.py
git commit -m "feat: validate editable PPTX generation"
```

### Task 4: STA PowerPoint Render Worker

**Files:**
- Create: `src/pptmaker/powerpoint/protocol.py`
- Create: `src/pptmaker/powerpoint/worker.py`
- Create: `src/pptmaker/powerpoint/client.py`
- Test: `tests/powerpoint/test_protocol.py`
- Test: `tests/powerpoint/test_worker_integration.py`

**Interfaces:**
- Consumes: `RenderRequest(run_id, idempotency_key, input_path, output_dir, timeout_seconds)`.
- Produces: `RenderResponse(status, owned_pid, slide_images, elapsed_seconds, error)`.

- [ ] **Step 1: Write protocol validation tests**

```python
# tests/powerpoint/test_protocol.py
import pytest
from pydantic import ValidationError

from pptmaker.powerpoint.protocol import RenderRequest


def test_render_request_rejects_non_absolute_input():
    with pytest.raises(ValidationError):
        RenderRequest(run_id="r1", idempotency_key="k1", input_path="relative.pptx", output_dir="C:/tmp/out")
```

- [ ] **Step 2: Implement protocol**

```python
# src/pptmaker/powerpoint/protocol.py
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RenderRequest(BaseModel):
    run_id: str
    idempotency_key: str
    input_path: str
    output_dir: str
    timeout_seconds: int = Field(default=60, ge=5, le=300)

    @field_validator("input_path", "output_dir")
    @classmethod
    def absolute_paths_only(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("path must be absolute")
        return value


class RenderResponse(BaseModel):
    status: Literal["success", "failed"]
    owned_pid: int | None = None
    slide_images: list[str] = []
    elapsed_seconds: float
    error: str | None = None
```

- [ ] **Step 3: Run protocol test**

Run: `conda run -n AI python -m pytest tests/powerpoint/test_protocol.py -v`  
Expected: PASS.

- [ ] **Step 4: Implement STA worker entry point**

```python
# src/pptmaker/powerpoint/worker.py
import json
import sys
import time
from pathlib import Path

import pythoncom
import win32com.client

from pptmaker.powerpoint.protocol import RenderRequest, RenderResponse


def render(request: RenderRequest) -> RenderResponse:
    started = time.perf_counter()
    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
    app = presentation = None
    try:
        output = Path(request.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        app = win32com.client.DispatchEx("PowerPoint.Application")
        app.Visible = True
        app.DisplayAlerts = 1
        presentation = app.Presentations.Open(request.input_path, ReadOnly=True, Untitled=False, WithWindow=False)
        presentation.Export(str(output), "PNG")
        images = sorted(str(path) for path in output.glob("*.PNG"))
        if not images:
            raise RuntimeError("PowerPoint exported no slide images")
        return RenderResponse(status="success", slide_images=images, elapsed_seconds=time.perf_counter() - started)
    except Exception as exc:
        return RenderResponse(status="failed", error=f"{type(exc).__name__}: {exc}", elapsed_seconds=time.perf_counter() - started)
    finally:
        if presentation is not None:
            presentation.Close()
        if app is not None:
            app.Quit()
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    request = RenderRequest.model_validate_json(sys.stdin.read())
    sys.stdout.write(render(request).model_dump_json())
```

- [ ] **Step 5: Implement hard-timeout client**

```python
# src/pptmaker/powerpoint/client.py
import subprocess
import sys

from pptmaker.powerpoint.protocol import RenderRequest, RenderResponse


def render_with_timeout(request: RenderRequest) -> RenderResponse:
    process = subprocess.Popen(
        [sys.executable, "-m", "pptmaker.powerpoint.worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(request.model_dump_json(), timeout=request.timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        return RenderResponse(status="failed", elapsed_seconds=float(request.timeout_seconds), error="worker hard timeout")
    if process.returncode != 0:
        return RenderResponse(status="failed", elapsed_seconds=0.0, error=stderr.strip() or "worker failed")
    return RenderResponse.model_validate_json(stdout)
```

- [ ] **Step 6: Add real Office integration test**

```python
# tests/powerpoint/test_worker_integration.py
from pathlib import Path

import pytest

from pptmaker.m0.pptx_probe import build_baseline_deck
from pptmaker.powerpoint.client import render_with_timeout
from pptmaker.powerpoint.protocol import RenderRequest


@pytest.mark.office
def test_powerpoint_exports_each_slide(tmp_path: Path):
    deck = (tmp_path / "baseline.pptx").resolve()
    render_dir = (tmp_path / "renders").resolve()
    build_baseline_deck(deck)
    response = render_with_timeout(RenderRequest(
        run_id="office-probe", idempotency_key="baseline-v1",
        input_path=str(deck), output_dir=str(render_dir), timeout_seconds=60,
    ))
    assert response.status == "success", response.error
    assert len(response.slide_images) == 2
```

- [ ] **Step 7: Run protocol and Office tests**

Run: `conda run -n AI python -m pytest tests/powerpoint -v -m "office or not office"`  
Expected: all tests PASS and two PNG files are exported.

- [ ] **Step 8: Record the M0 limitation**

Add to `artifacts/m0/powerpoint-worker.json` that heartbeat, PID ownership via WMI, cancellation, protected-view detection, and atomic final-file replacement remain production tasks. M0 proves STA isolation, serialization, hard timeout, cleanup, and rendering only.

- [ ] **Step 9: Commit**

```powershell
git add src/pptmaker/powerpoint tests/powerpoint
git commit -m "feat: validate isolated PowerPoint rendering"
```

### Task 5: Deterministic Geometry Checks

**Files:**
- Create: `src/pptmaker/evaluation/geometry.py`
- Test: `tests/evaluation/test_geometry.py`

**Interfaces:**
- Consumes: `Box(x, y, width, height)` in English Metric Units.
- Produces: `out_of_bounds(box, canvas) -> bool` and `overlap_ratio(left, right) -> float`.

- [ ] **Step 1: Write boundary and overlap tests**

```python
# tests/evaluation/test_geometry.py
from pptmaker.evaluation.geometry import Box, out_of_bounds, overlap_ratio


def test_detects_right_overflow():
    assert out_of_bounds(Box(90, 10, 20, 20), Box(0, 0, 100, 100))


def test_overlap_ratio_uses_smaller_box_area():
    assert overlap_ratio(Box(0, 0, 10, 10), Box(5, 0, 10, 10)) == 0.5


def test_touching_edges_do_not_overlap():
    assert overlap_ratio(Box(0, 0, 10, 10), Box(10, 0, 10, 10)) == 0.0
```

- [ ] **Step 2: Implement pure geometry functions**

```python
# src/pptmaker/evaluation/geometry.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    width: int
    height: int


def out_of_bounds(box: Box, canvas: Box) -> bool:
    return (
        box.x < canvas.x or box.y < canvas.y
        or box.x + box.width > canvas.x + canvas.width
        or box.y + box.height > canvas.y + canvas.height
    )


def overlap_ratio(left: Box, right: Box) -> float:
    width = max(0, min(left.x + left.width, right.x + right.width) - max(left.x, right.x))
    height = max(0, min(left.y + left.height, right.y + right.height) - max(left.y, right.y))
    intersection = width * height
    denominator = min(left.width * left.height, right.width * right.height)
    return 0.0 if denominator == 0 else intersection / denominator
```

- [ ] **Step 3: Run tests and commit**

Run: `conda run -n AI python -m pytest tests/evaluation/test_geometry.py -v`  
Expected: three passing tests.

```powershell
git add src/pptmaker/evaluation tests/evaluation
git commit -m "feat: add deterministic geometry probes"
```

### Task 6: Upload and SSRF Security Core

**Files:**
- Create: `src/pptmaker/security/uploads.py`
- Create: `src/pptmaker/security/network.py`
- Test: `tests/security/test_uploads.py`
- Test: `tests/security/test_network.py`

**Interfaces:**
- Consumes: uploaded path or resolved IP string.
- Produces: `inspect_zip(path, limits) -> ArchiveInspection` and `is_forbidden_ip(value) -> bool`.

- [ ] **Step 1: Write ZIP traversal and expansion tests**

```python
# tests/security/test_uploads.py
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from pptmaker.security.uploads import ArchiveLimits, UnsafeArchive, inspect_zip


def test_rejects_path_traversal(tmp_path: Path):
    archive = tmp_path / "bad.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as handle:
        handle.writestr("../escape.txt", "x")
    with pytest.raises(UnsafeArchive, match="path traversal"):
        inspect_zip(archive, ArchiveLimits())


def test_rejects_excessive_uncompressed_size(tmp_path: Path):
    archive = tmp_path / "large.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as handle:
        handle.writestr("large.txt", "x" * 2048)
    with pytest.raises(UnsafeArchive, match="uncompressed size"):
        inspect_zip(archive, ArchiveLimits(max_uncompressed_bytes=1024))
```

- [ ] **Step 2: Implement non-extracting archive inspection**

```python
# src/pptmaker/security/uploads.py
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile


class UnsafeArchive(ValueError):
    pass


@dataclass(frozen=True)
class ArchiveLimits:
    max_members: int = 5000
    max_uncompressed_bytes: int = 200 * 1024 * 1024
    max_ratio: float = 200.0


@dataclass(frozen=True)
class ArchiveInspection:
    members: int
    compressed_bytes: int
    uncompressed_bytes: int


def inspect_zip(path: Path, limits: ArchiveLimits) -> ArchiveInspection:
    try:
        with ZipFile(path) as archive:
            members = archive.infolist()
    except BadZipFile as exc:
        raise UnsafeArchive("invalid ZIP container") from exc
    if len(members) > limits.max_members:
        raise UnsafeArchive("member count exceeds limit")
    for member in members:
        candidate = PurePosixPath(member.filename.replace("\\", "/"))
        if candidate.is_absolute() or ".." in candidate.parts:
            raise UnsafeArchive("path traversal detected")
    compressed = sum(member.compress_size for member in members)
    uncompressed = sum(member.file_size for member in members)
    if uncompressed > limits.max_uncompressed_bytes:
        raise UnsafeArchive("uncompressed size exceeds limit")
    ratio = uncompressed / max(compressed, 1)
    if ratio > limits.max_ratio:
        raise UnsafeArchive("compression ratio exceeds limit")
    return ArchiveInspection(len(members), compressed, uncompressed)
```

- [ ] **Step 3: Write forbidden-address tests**

```python
# tests/security/test_network.py
import pytest

from pptmaker.security.network import is_forbidden_ip


@pytest.mark.parametrize("value", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1"])
def test_blocks_non_public_addresses(value: str):
    assert is_forbidden_ip(value)


def test_allows_public_address():
    assert not is_forbidden_ip("1.1.1.1")
```

- [ ] **Step 4: Implement IP classification**

```python
# src/pptmaker/security/network.py
from ipaddress import ip_address


def is_forbidden_ip(value: str) -> bool:
    address = ip_address(value)
    return not address.is_global
```

- [ ] **Step 5: Run tests and commit**

Run: `conda run -n AI python -m pytest tests/security -v`  
Expected: all tests PASS.

```powershell
git add src/pptmaker/security tests/security
git commit -m "feat: validate upload and SSRF defenses"
```

### Task 7: DeepSeek Structured-Output Probe

**Files:**
- Create: `.env.example`
- Create: `src/pptmaker/m0/deepseek_probe.py`
- Test: `tests/m0/test_deepseek_probe.py`

**Interfaces:**
- Consumes: `DEEPSEEK_API_KEY`, optional `DEEPSEEK_BASE_URL`, and model name.
- Produces: validated `OutlineProbe` and latency/usage metrics; never stores the key.

- [ ] **Step 1: Define safe environment documentation**

```dotenv
# .env.example
DEEPSEEK_API_KEY=replace-in-local-environment-only
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

- [ ] **Step 2: Write parser tests**

```python
# tests/m0/test_deepseek_probe.py
import pytest
from pydantic import ValidationError

from pptmaker.m0.deepseek_probe import OutlineProbe, parse_outline


def test_parses_valid_outline():
    value = parse_outline('{"title":"项目汇报","slides":["背景","方案","结果"]}')
    assert value.slides == ["背景", "方案", "结果"]


def test_rejects_too_short_outline():
    with pytest.raises(ValidationError):
        parse_outline('{"title":"项目汇报","slides":["背景"]}')
```

- [ ] **Step 3: Implement schema, parser, and explicit online probe**

```python
# src/pptmaker/m0/deepseek_probe.py
import json
import os
import time

from openai import OpenAI
from pydantic import BaseModel, Field


class OutlineProbe(BaseModel):
    title: str
    slides: list[str] = Field(min_length=3, max_length=12)


def parse_outline(raw: str) -> OutlineProbe:
    return OutlineProbe.model_validate_json(raw)


def run_online_probe() -> tuple[OutlineProbe, dict[str, float | int | str]]:
    key = os.environ["DEEPSEEK_API_KEY"]
    client = OpenAI(api_key=key, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        temperature=0,
        messages=[
            {"role": "system", "content": "仅输出JSON，字段为title和slides；slides包含3到12个中文页面标题。"},
            {"role": "user", "content": "为一个中文AI PPT生成器项目生成项目汇报大纲。"},
        ],
    )
    outline = parse_outline(response.choices[0].message.content or "")
    usage = response.usage
    return outline, {
        "latency_seconds": time.perf_counter() - started,
        "model": response.model,
        "prompt_tokens": int(usage.prompt_tokens if usage else 0),
        "completion_tokens": int(usage.completion_tokens if usage else 0),
    }
```

- [ ] **Step 4: Run offline tests**

Run: `conda run -n AI python -m pytest tests/m0/test_deepseek_probe.py -v`  
Expected: two passing tests without requiring a key.

- [ ] **Step 5: Run online probe without exposing the key**

Set `DEEPSEEK_API_KEY` in the current terminal or Windows Credential Manager, then run:

```powershell
conda run -n AI python -c "from pptmaker.m0.deepseek_probe import run_online_probe; print(run_online_probe())"
```

Expected: a validated Chinese outline plus latency and token metrics. If JSON validation fails, record FAIL rather than adding an unbounded retry.

- [ ] **Step 6: Commit**

```powershell
git add .env.example src/pptmaker/m0/deepseek_probe.py tests/m0/test_deepseek_probe.py
git commit -m "feat: probe DeepSeek structured output"
```

### Task 8: Parser Capability Matrix

**Files:**
- Create: `src/pptmaker/m0/parser_probe.py`
- Create: `tests/fixtures/documents/generate.py`
- Create: `tests/fixtures/documents/README.md`
- Test: `tests/m0/test_parser_probe.py`
- Create: `docs/evaluations/m0-parser-matrix.md`

**Interfaces:**
- Consumes: synthetic Markdown, DOCX, PDF, PPTX, and PNG fixtures generated by tests.
- Produces: `ParsedDocument(kind, text, tables, images, locations)` and a measured matrix.

- [ ] **Step 1: Define the normalized probe result and Markdown parser test**

```python
# tests/m0/test_parser_probe.py
from pptmaker.m0.parser_probe import parse_markdown


def test_markdown_preserves_heading_and_table():
    parsed = parse_markdown("# 结论\n\n|指标|值|\n|---|---|\n|质量|90|\n")
    assert parsed.kind == "markdown"
    assert "结论" in parsed.text
    assert parsed.tables == [["指标", "值"], ["质量", "90"]]
```

- [ ] **Step 2: Implement the normalized result and deterministic Markdown parser**

```python
# src/pptmaker/m0/parser_probe.py
from pydantic import BaseModel, Field


class ParsedDocument(BaseModel):
    kind: str
    text: str
    tables: list[list[str]] = Field(default_factory=list)
    images: int = 0
    locations: list[str] = Field(default_factory=list)


def parse_markdown(content: str) -> ParsedDocument:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    text = "\n".join(line.lstrip("# ") for line in lines if not line.startswith("|"))
    table_rows = []
    for line in lines:
        if line.startswith("|") and "---" not in line:
            table_rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return ParsedDocument(kind="markdown", text=text, tables=table_rows)
```

- [ ] **Step 3: Run the test**

Run: `conda run -n AI python -m pytest tests/m0/test_parser_probe.py -v`  
Expected: PASS.

- [ ] **Step 4: Add parsing dependencies to `pyproject.toml`**

Append these exact entries to `[project].dependencies`:

```toml
  "python-docx==1.2.0",
  "pypdf==6.9.1",
  "reportlab==4.4.10",
  "markitdown==0.1.5",
```

- [ ] **Step 5: Generate deterministic DOCX, PDF, PPTX, and PNG fixtures**

```python
# tests/fixtures/documents/generate.py
from pathlib import Path

from docx import Document
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.util import Inches
from reportlab.pdfgen.canvas import Canvas


SENTINEL = "M0_SOURCE_SENTINEL_20260722"


def generate(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "sample.md").write_text(f"# M0\n\n{SENTINEL}\n", "utf-8")

    image = Image.new("RGB", (320, 180), "white")
    ImageDraw.Draw(image).text((20, 80), SENTINEL, fill="black")
    image.save(root / "sample.png")

    doc = Document()
    doc.add_heading("M0", 1)
    doc.add_paragraph(SENTINEL)
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "指标", "值"
    table.cell(1, 0).text, table.cell(1, 1).text = "质量", "90"
    doc.save(root / "sample.docx")

    pdf = Canvas(str(root / "sample.pdf"))
    pdf.drawString(72, 760, SENTINEL)
    pdf.showPage()
    pdf.save()

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(1)).text = SENTINEL
    prs.save(root / "sample.pptx")


if __name__ == "__main__":
    generate(Path(__file__).parent)
```

- [ ] **Step 6: Add a MarkItDown comparison path**

Append to `src/pptmaker/m0/parser_probe.py`:

```python
from pathlib import Path

from markitdown import MarkItDown


def parse_with_markitdown(path: Path) -> ParsedDocument:
    result = MarkItDown().convert(str(path))
    return ParsedDocument(kind=path.suffix.lstrip(".").lower(), text=result.text_content)
```

Append to `tests/m0/test_parser_probe.py`:

```python
from pathlib import Path

import pytest

from pptmaker.m0.parser_probe import parse_with_markitdown
from tests.fixtures.documents.generate import SENTINEL, generate


@pytest.mark.parametrize("name", ["sample.docx", "sample.pdf", "sample.pptx", "sample.png"])
def test_markitdown_extracts_or_explicitly_reports_sentinel(tmp_path: Path, name: str):
    generate(tmp_path)
    parsed = parse_with_markitdown(tmp_path / name)
    if name == "sample.png":
        pytest.xfail("Image OCR requires an explicitly configured multimodal provider")
    assert SENTINEL in parsed.text
```

- [ ] **Step 7: Install, generate fixtures, and run the matrix tests**

Run:

```powershell
conda run -n AI python -m pip install -e ".[test]"
conda run -n AI python tests/fixtures/documents/generate.py
conda run -n AI python -m pytest tests/m0/test_parser_probe.py -v
```

Expected: one explicit PASS/FAIL row per format. Record extraction fidelity, location preservation, elapsed time, and dependency used in `docs/evaluations/m0-parser-matrix.md`.

- [ ] **Step 8: Commit**

```powershell
git add pyproject.toml src/pptmaker/m0/parser_probe.py tests/m0/test_parser_probe.py tests/fixtures/documents docs/evaluations/m0-parser-matrix.md
git commit -m "test: measure document parser capabilities"
```

### Task 9: Vision-Model Benchmark Harness

**Files:**
- Create: `src/pptmaker/m0/vision_schema.py`
- Create: `src/pptmaker/m0/vision_metrics.py`
- Create: `benchmarks/vision/generate_cases.py`
- Create: `benchmarks/vision/m0_manifest.jsonl`
- Create: `benchmarks/vision/README.md`
- Test: `tests/m0/test_vision_metrics.py`
- Create: `docs/evaluations/m0-vision-models.md`

**Interfaces:**
- Consumes: frozen expected issue labels and model JSON predictions.
- Produces: precision, recall, F1, false-positive rate, JSON validity, latency, and peak VRAM per model.

- [ ] **Step 1: Write metric tests**

```python
# tests/m0/test_vision_metrics.py
from pptmaker.m0.vision_metrics import score_labels


def test_scores_true_false_positive_and_false_negative():
    score = score_labels(expected={"overflow", "crowded"}, predicted={"overflow", "irrelevant_image"})
    assert score.true_positive == 1
    assert score.false_positive == 1
    assert score.false_negative == 1
    assert score.precision == 0.5
    assert score.recall == 0.5
```

- [ ] **Step 2: Implement issue schema and metrics**

```python
# src/pptmaker/m0/vision_schema.py
from typing import Literal

from pydantic import BaseModel, Field


class VisionIssue(BaseModel):
    type: str
    severity: Literal["low", "medium", "high"]
    region: str
    evidence: str
    suggestion: str
    confidence: float = Field(ge=0, le=1)


class VisionReview(BaseModel):
    slide_id: str
    issues: list[VisionIssue]
    overall_score: int = Field(ge=0, le=100)
```

```python
# src/pptmaker/m0/vision_metrics.py
from dataclasses import dataclass


@dataclass(frozen=True)
class LabelScore:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float


def score_labels(expected: set[str], predicted: set[str]) -> LabelScore:
    tp = len(expected & predicted)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return LabelScore(tp, fp, fn, precision, recall)
```

- [ ] **Step 3: Run metric tests**

Run: `conda run -n AI python -m pytest tests/m0/test_vision_metrics.py -v`  
Expected: PASS.

- [ ] **Step 4: Create deterministic visual cases**

```python
# benchmarks/vision/generate_cases.py
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def create_cases(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    normal = Image.new("RGB", (1280, 720), "white")
    draw = ImageDraw.Draw(normal)
    draw.text((80, 60), "Clear project summary", font=font, fill="black")
    draw.rectangle((80, 180, 560, 580), outline="#1f4e79", width=4)
    normal.save(output / "normal_001.png")

    overflow = normal.copy()
    ImageDraw.Draw(overflow).text((1180, 680), "TEXT_OUTSIDE_SAFE_MARGIN", font=font, fill="red")
    overflow.save(output / "overflow_001.png")

    crowded = Image.new("RGB", (1280, 720), "white")
    crowded_draw = ImageDraw.Draw(crowded)
    for index in range(30):
        y = 20 + index * 22
        crowded_draw.text((30, y), f"Dense line {index}: repeated content without hierarchy", font=font, fill="black")
    crowded.save(output / "crowded_001.png")


if __name__ == "__main__":
    create_cases(Path("artifacts/m0/vision"))
```

Run: `conda run -n AI python benchmarks/vision/generate_cases.py`  
Expected: three deterministic PNG files under the ignored `artifacts/m0/vision/` directory.

- [ ] **Step 5: Create the benchmark manifest**

```json
{"case_id":"normal_001","split":"development","image":"artifacts/m0/vision/normal_001.png","expected":[],"license":"synthetic"}
{"case_id":"overflow_001","split":"development","image":"artifacts/m0/vision/overflow_001.png","expected":["overflow"],"license":"synthetic"}
{"case_id":"crowded_001","split":"validation","image":"artifacts/m0/vision/crowded_001.png","expected":["crowded"],"license":"synthetic"}
```

The initial manifest validates the harness. Before model selection, add PowerPoint-rendered cases for every defect class and record SHA-256 hashes. Do not commit PNG output; commit only generators, expected labels, and hashes.

- [ ] **Step 6: Benchmark candidates sequentially**

Run each model with batch size 1 and identical prompt/schema:

- existing `models/QwenQwen3-VL-4B-Instruct` in 4-bit;
- Qwen3-VL-2B-Instruct;
- MiniCPM-V-4.6;
- InternVL3.5-2B.

For each model, record JSON validity, precision, recall, false-positive rate, P50/P95 per-slide latency, and CUDA peak memory in `docs/evaluations/m0-vision-models.md`. If a model cannot load on 8 GB VRAM, record BLOCKED with the exception and attempted quantization; do not silently offload unless CPU-offload is a separately measured row.

- [ ] **Step 7: Commit harness and report**

```powershell
git add src/pptmaker/m0/vision_schema.py src/pptmaker/m0/vision_metrics.py tests/m0/test_vision_metrics.py benchmarks/vision docs/evaluations/m0-vision-models.md
git commit -m "test: add PPT vision model benchmark"
```

### Task 10: Search and Image Provider Decision Probe

**Files:**
- Create: `src/pptmaker/research/contracts.py`
- Test: `tests/research/test_contracts.py`
- Create: `docs/evaluations/m0-search-and-assets.md`

**Interfaces:**
- Consumes: keyed search provider credentials or explicit user URLs.
- Produces: normalized `SearchResult` and `AssetCandidate` with provenance and license status.

- [ ] **Step 1: Write provenance contract tests**

```python
# tests/research/test_contracts.py
import pytest
from pydantic import ValidationError

from pptmaker.research.contracts import AssetCandidate, LicenseStatus


def test_asset_requires_source_url_and_access_date():
    with pytest.raises(ValidationError):
        AssetCandidate(url="https://example.com/a.jpg", license_status=LicenseStatus.UNKNOWN)
```

- [ ] **Step 2: Implement normalized contracts**

```python
# src/pptmaker/research/contracts.py
from datetime import date
from enum import Enum

from pydantic import BaseModel, HttpUrl


class LicenseStatus(str, Enum):
    REUSABLE = "reusable"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    snippet: str
    provider: str


class AssetCandidate(BaseModel):
    url: HttpUrl
    source_page: HttpUrl
    author: str | None = None
    license_name: str | None = None
    license_status: LicenseStatus
    accessed_at: date
```

- [ ] **Step 3: Run tests**

Run: `conda run -n AI python -m pytest tests/research/test_contracts.py -v`  
Expected: PASS.

- [ ] **Step 4: Measure providers without selecting by reputation**

Evaluate at least two keyed search candidates usable from China and at least two image sources with explicit API/license terms. Run these fixed queries exactly: `2025中国生成式AI市场规模 官方数据`, `中国企业数字化转型统计报告`, `人工智能项目实施路线图`, `PowerPoint可访问性规范`, `北京常住人口 官方统计`, `新能源汽车销量 中国汽车工业协会`, `免费可商用 人工智能 办公 图片`, `免费可商用 团队协作 图片`, `科技蓝 抽象背景 免费商用`, `数据分析 图标 免费商用`. Record availability, free quota, top-five Chinese relevance, duplicate rate, source-domain count, P50 latency over three runs, terms URL, attribution fields, and HTTP failure behavior in `docs/evaluations/m0-search-and-assets.md`.

The formal M0 path must fail closed when no key is configured. Manual URL ingestion is evaluated separately. No-key scraping is an experimental row and cannot win the default-provider decision.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/research tests/research docs/evaluations/m0-search-and-assets.md
git commit -m "test: evaluate search and asset providers"
```

### Task 11: M0 Gate Report and ADRs

**Files:**
- Create: `docs/adr/0001-pptx-and-powerpoint-rendering.md`
- Create: `docs/adr/0002-document-parser-selection.md`
- Create: `docs/adr/0003-local-vision-model-selection.md`
- Create: `docs/adr/0004-search-and-asset-provider-selection.md`
- Create: `docs/evaluations/m0-gate-report.md`
- Create: `scripts/check_m0_gate.py`
- Test: `tests/scripts/test_check_m0_gate.py`

**Interfaces:**
- Consumes: required JSON probe results under `artifacts/m0/`.
- Produces: nonzero exit when mandatory evidence is missing or failed.

- [ ] **Step 1: Write gate checker test**

```python
# tests/scripts/test_check_m0_gate.py
import json
from pathlib import Path

from scripts.check_m0_gate import check_gate


def test_gate_fails_when_mandatory_probe_failed(tmp_path: Path):
    folder = tmp_path / "artifacts" / "m0"
    folder.mkdir(parents=True)
    (folder / "pptx-baseline.json").write_text(json.dumps({"status": "fail"}), "utf-8")
    failures = check_gate(tmp_path, required=("pptx-baseline",))
    assert failures == ["pptx-baseline: fail"]
```

- [ ] **Step 2: Implement deterministic gate checker**

```python
# scripts/check_m0_gate.py
import json
import sys
from pathlib import Path


REQUIRED = ("pptx-baseline", "powerpoint-worker", "upload-security", "deepseek-structured-output")


def check_gate(root: Path, required: tuple[str, ...] = REQUIRED) -> list[str]:
    failures = []
    for name in required:
        path = root / "artifacts" / "m0" / f"{name}.json"
        if not path.exists():
            failures.append(f"{name}: missing")
            continue
        status = json.loads(path.read_text("utf-8")).get("status")
        if status != "pass":
            failures.append(f"{name}: {status}")
    return failures


if __name__ == "__main__":
    errors = check_gate(Path.cwd())
    for error in errors:
        print(error)
    raise SystemExit(1 if errors else 0)
```

- [ ] **Step 3: Run checker tests**

Run: `conda run -n AI python -m pytest tests/scripts/test_check_m0_gate.py -v`  
Expected: PASS.

- [ ] **Step 4: Write evidence-based ADRs and gate report**

Each ADR must contain context, measured alternatives, decision, rejected alternatives, consequences, rollback trigger, and links to machine-readable evidence. `m0-gate-report.md` must list every probe command, environment versions, pass/fail/block status, known risks, changed assumptions, and the exact M1 entry criteria.

- [ ] **Step 5: Run the complete M0 suite**

```powershell
conda run -n AI python -m pytest -v
conda run -n AI python scripts/check_m0_gate.py
```

Expected: all offline and Office tests PASS; gate checker exits 0. Online/provider/model experiments may be marked BLOCKED only if they are explicitly non-mandatory in the report. DeepSeek structured-output is mandatory before M1.

- [ ] **Step 6: Human M0 review**

Open `artifacts/m0/baseline.pptx`, inspect exported PNGs, and review the parser, vision, search, security, and timing reports. Record the user's decision and corrections in `docs/evaluations/m0-gate-report.md`.

- [ ] **Step 7: Commit**

```powershell
git add docs/adr docs/evaluations/m0-gate-report.md scripts/check_m0_gate.py tests/scripts/test_check_m0_gate.py
git commit -m "docs: complete M0 technical validation gate"
```
