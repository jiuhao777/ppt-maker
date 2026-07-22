# M0 Technical Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce reproducible evidence for the highest-risk PPT-maker decisions before building the product workflow.

**Architecture:** Build small probes behind stable contracts, not production subsystems. Each probe writes machine-readable results under `artifacts/m0/`; the final gate converts those results into ADRs and a go/no-go report.

**Tech Stack:** Conda `AI` currently locked to Python 3.10.20, project support range Python >=3.10,<3.13, pytest, Pydantic 2.13.4, python-pptx, pywin32, OpenAI SDK 2.45.0, httpx 0.28.1, Pillow 12.3.0, Torch 2.6.0+cu124, Transformers 4.56.0, Microsoft PowerPoint.

## Global Constraints

- Execute Python as `conda run -n AI python ...` and tests as `conda run -n AI python -m pytest ...`.
- Use only synthetic content or license-recorded public fixtures.
- Never commit API keys, downloaded model weights, generated output, temporary Office files, or public assets.
- A probe failure is a valid M0 result; do not hide it with fallback behavior.
- PowerPoint automation must run in STA and may terminate only the exact PID it owns.
- Network tests must reject loopback, private, link-local, reserved, and cloud metadata targets.
- Commit after every task that passes its own gate.

## M0 Gate Classification

Mandatory evidence: editable PPTX generation, PowerPoint rendering plus owned-process timeout cleanup, geometry checks, upload/SSRF baseline security, DeepSeek repeated structured output, and Markdown/PPTX parsing. Every mandatory probe must write a `ProbeResult` JSON through `execute_probe`.

Exploratory evidence: final parser selection beyond Markdown/PPTX, final local vision-model selection, search/image provider selection, CPU vision fallback, and animation capability. Exploratory failure or missing credentials does not block M1, but the report must preserve the failure and its consequence.

---

### Task 1: Repository and M0 Test Foundation

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `src/pptmaker/__init__.py`
- Create: `requirements/ai-py310-win.lock.txt`
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
    assert (3, 10) <= sys.version_info[:2] < (3, 13)
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
requires-python = ">=3.10,<3.13"
dependencies = [
  "pydantic==2.13.4",
  "python-pptx==1.0.2",
  "pywin32==311; sys_platform == 'win32'",
  "Pillow==12.3.0",
  "httpx==0.28.1",
  "openai==2.45.0",
  "psutil==7.1.3",
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
conda run -n AI python -m pip freeze | Set-Content -Encoding UTF8 requirements/ai-py310-win.lock.txt
```

Expected: one passing test and no unknown-marker warning.

- [ ] **Step 6: Commit**

```powershell
git add .gitignore pyproject.toml requirements/ai-py310-win.lock.txt src/pptmaker/__init__.py tests/conftest.py tests/test_environment.py
git commit -m "chore: establish M0 test foundation"
```

### Task 2: Artifact and Probe Result Contracts

**Files:**
- Create: `src/pptmaker/m0/contracts.py`
- Create: `src/pptmaker/m0/artifacts.py`
- Test: `tests/m0/test_artifacts.py`

**Interfaces:**
- Consumes: a repository root and probe name.
- Produces: `ProbeResult`, `write_probe_result(result, root) -> Path`, and `execute_probe(name, runner, root) -> Path`.

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


def execute_probe(name: str, runner, root: Path) -> Path:
    try:
        result = runner()
        if result.name != name:
            raise ValueError(f"probe returned unexpected name: {result.name}")
    except Exception as exc:
        result = ProbeResult(
            name=name,
            status="fail",
            limitations=[f"{type(exc).__name__}: {exc}"],
        )
    return write_probe_result(result, root)
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
conda run -n AI python -c "from pathlib import Path; from pptmaker.m0.artifacts import execute_probe; from pptmaker.m0.pptx_probe import build_baseline_deck; root=Path.cwd(); execute_probe('pptx-baseline', lambda: build_baseline_deck(root/'artifacts/m0/baseline.pptx'), root)"
```

Expected: PASS, `artifacts/m0/baseline.pptx` exists, and `artifacts/m0/pptx-baseline.json` has status `pass`.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/m0/pptx_probe.py tests/m0/test_pptx_probe.py
git commit -m "feat: validate editable PPTX generation"
```

### Task 4: STA PowerPoint Render Worker

**Files:**
- Create: `src/pptmaker/powerpoint/protocol.py`
- Create: `src/pptmaker/powerpoint/preflight.py`
- Create: `src/pptmaker/powerpoint/worker.py`
- Create: `src/pptmaker/powerpoint/client.py`
- Test: `tests/powerpoint/test_protocol.py`
- Test: `tests/powerpoint/test_preflight.py`
- Test: `tests/powerpoint/test_worker_integration.py`

**Interfaces:**
- Consumes: `RenderRequest(run_id, idempotency_key, input_path, output_dir, control_path, cancel_path, timeout_seconds)`.
- Produces: `RenderResponse(status, owned_pid, slide_images, elapsed_seconds, error)`.

- [ ] **Step 1: Write protocol validation tests**

```python
# tests/powerpoint/test_protocol.py
import pytest
from pydantic import ValidationError

from pptmaker.powerpoint.protocol import RenderRequest


def test_render_request_rejects_non_absolute_input():
    with pytest.raises(ValidationError):
        RenderRequest(
            run_id="r1", idempotency_key="k1", input_path="relative.pptx", output_dir="C:/tmp/out",
            control_path="C:/tmp/control.json", cancel_path="C:/tmp/cancel.flag",
        )
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
    elapsed_seconds: float
    error: str | None = None
```

- [ ] **Step 3: Run protocol test**

Run: `conda run -n AI python -m pytest tests/powerpoint/test_protocol.py -v`  
Expected: PASS.

- [ ] **Step 3a: Implement and test PowerPoint preflight**

```python
# src/pptmaker/powerpoint/preflight.py
from pathlib import Path

import psutil
import win32con
import win32file


def preflight_issues(path: Path) -> list[str]:
    issues = []
    zone_path = Path(f"{path}:Zone.Identifier")
    try:
        zone = zone_path.read_text("utf-8", errors="ignore")
        if "ZoneId=3" in zone or "ZoneId=4" in zone:
            issues.append("protected_view_risk")
    except OSError:
        pass
    try:
        handle = win32file.CreateFile(
            str(path), win32con.GENERIC_READ, 0, None, win32con.OPEN_EXISTING,
            win32con.FILE_ATTRIBUTE_NORMAL, None,
        )
        handle.Close()
    except OSError:
        issues.append("file_locked")
    existing = [
        process.pid for process in psutil.process_iter(["name"])
        if (process.info["name"] or "").lower() == "powerpnt.exe"
    ]
    if existing:
        issues.append("existing_powerpoint_instance")
    return issues
```

`tests/powerpoint/test_preflight.py` must cover a synthetic `Zone.Identifier` stream where supported, a file held open with exclusive sharing, and an injected process iterator containing `POWERPNT.EXE`. The formal M0 Office test starts only when no PowerPoint instance is already open. Existing-instance behavior remains an exploratory compatibility test and must never terminate or attach to that instance. Record Office version, bitness, and macro-security mode in `powerpoint-worker.json`.

- [ ] **Step 4: Implement STA worker entry point**

```python
# src/pptmaker/powerpoint/worker.py
import json
import os
import sys
import threading
import time
from pathlib import Path

import pythoncom
import win32com.client
import win32process

from pptmaker.powerpoint.protocol import RenderRequest, RenderResponse
from pptmaker.powerpoint.preflight import preflight_issues


def _heartbeat(path: Path, pid: int, run_id: str, stop: threading.Event) -> None:
    while not stop.wait(1.0):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"pid": pid, "run_id": run_id, "heartbeat": time.time()}), "utf-8")
        os.replace(temporary, path)


def render(request: RenderRequest) -> RenderResponse:
    started = time.perf_counter()
    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
    app = presentation = None
    owned_pid = None
    primary_error = None
    heartbeat_stop = threading.Event()
    heartbeat_thread = None
    try:
        issues = preflight_issues(Path(request.input_path))
        if issues:
            raise RuntimeError("PowerPoint preflight failed: " + ",".join(issues))
        if Path(request.cancel_path).exists():
            raise RuntimeError("task cancelled before PowerPoint launch")
        output = Path(request.output_dir) / request.run_id
        output.mkdir(parents=True, exist_ok=True)
        app = win32com.client.DispatchEx("PowerPoint.Application")
        _, owned_pid = win32process.GetWindowThreadProcessId(app.HWND)
        control = Path(request.control_path)
        control.parent.mkdir(parents=True, exist_ok=True)
        temporary = control.with_suffix(".tmp")
        temporary.write_text(json.dumps({"pid": owned_pid, "run_id": request.run_id}), "utf-8")
        os.replace(temporary, control)
        heartbeat_thread = threading.Thread(
            target=_heartbeat, args=(control, owned_pid, request.run_id, heartbeat_stop), daemon=True
        )
        heartbeat_thread.start()
        if Path(request.cancel_path).exists():
            raise RuntimeError("task cancelled before PowerPoint open")
        if request.test_hold_seconds:
            time.sleep(request.test_hold_seconds)
        app.Visible = True
        app.DisplayAlerts = 1
        presentation = app.Presentations.Open(request.input_path, ReadOnly=True, Untitled=False, WithWindow=False)
        presentation.Export(str(output), "PNG")
        if Path(request.cancel_path).exists():
            raise RuntimeError("task cancelled after PowerPoint export")
        images = sorted(
            (str(path) for path in output.glob("*.PNG")),
            key=lambda value: int("".join(filter(str.isdigit, Path(value).stem)) or 0),
        )
        if not images:
            raise RuntimeError("PowerPoint exported no slide images")
        return RenderResponse(status="success", owned_pid=owned_pid, slide_images=images, elapsed_seconds=time.perf_counter() - started)
    except Exception as exc:
        primary_error = f"{type(exc).__name__}: {exc}"
        return RenderResponse(status="failed", owned_pid=owned_pid, error=primary_error, elapsed_seconds=time.perf_counter() - started)
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
import json
from pathlib import Path

import psutil
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
        control = Path(request.control_path)
        if control.exists():
            owned = json.loads(control.read_text("utf-8"))
            if owned.get("run_id") == request.run_id:
                try:
                    powerpoint = psutil.Process(int(owned["pid"]))
                    if powerpoint.name().lower() == "powerpnt.exe":
                        powerpoint.terminate()
                        try:
                            powerpoint.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            powerpoint.kill()
                            powerpoint.wait(timeout=5)
                except psutil.NoSuchProcess:
                    pass
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
        input_path=str(deck), output_dir=str(render_dir),
        control_path=str((tmp_path / "control.json").resolve()),
        cancel_path=str((tmp_path / "cancel.flag").resolve()), timeout_seconds=60,
    ))
    assert response.status == "success", response.error
    assert len(response.slide_images) == 2
```

Add two further integration tests in the same file:

```python
import psutil
import time
import json


@pytest.mark.office
def test_timeout_leaves_no_owned_powerpoint_process(tmp_path: Path):
    deck = (tmp_path / "baseline.pptx").resolve()
    build_baseline_deck(deck)
    control = (tmp_path / "timeout-control.json").resolve()
    request = RenderRequest(
        run_id="timeout-probe", idempotency_key="timeout-v1",
        input_path=str(deck),
        output_dir=str((tmp_path / "renders").resolve()),
        control_path=str(control), cancel_path=str((tmp_path / "cancel.flag").resolve()),
        timeout_seconds=5, test_hold_seconds=15,
    )
    response = render_with_timeout(request)
    assert response.status == "failed"
    if control.exists():
        pid = int(json.loads(control.read_text("utf-8"))["pid"])
        time.sleep(0.5)
        assert not psutil.pid_exists(pid)


@pytest.mark.office
def test_timeout_does_not_terminate_preexisting_powerpoint(tmp_path: Path):
    existing = {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "powerpnt.exe"}
    test_timeout_leaves_no_owned_powerpoint_process(tmp_path)
    assert all(psutil.pid_exists(pid) for pid in existing)
```

Add a cancellation integration test that creates `cancel_path` before launch and asserts status `failed`, error contains `cancelled`, and the recorded owned PID no longer exists. Add a heartbeat test with `test_hold_seconds=5` and `timeout_seconds=15`: start the client in a background thread, read `control_path` twice at least 1.5 seconds apart, and assert the second `heartbeat` value is greater. These tests prove the control channel rather than merely checking fields.

- [ ] **Step 7: Run protocol and Office tests**

Run: `conda run -n AI python -m pytest tests/powerpoint -v -m "office or not office"`  
Expected: all tests PASS and two PNG files are exported.

- [ ] **Step 8: Record the M0 limitation**

Create the machine-readable probe:

```python
# src/pptmaker/m0/powerpoint_probe.py
import json
from pathlib import Path

import psutil

from pptmaker.m0.contracts import ProbeResult, ProbeStatus
from pptmaker.m0.pptx_probe import build_baseline_deck
from pptmaker.powerpoint.client import render_with_timeout
from pptmaker.powerpoint.protocol import RenderRequest


def run_powerpoint_probe(root: Path) -> ProbeResult:
    work = (root / "artifacts" / "m0" / "powerpoint-probe").resolve()
    work.mkdir(parents=True, exist_ok=True)
    deck = (work / "baseline.pptx").resolve()
    build_baseline_deck(deck)
    normal = render_with_timeout(RenderRequest(
        run_id="normal", idempotency_key="normal-v1", input_path=str(deck),
        output_dir=str(work), control_path=str(work / "normal-control.json"),
        cancel_path=str(work / "normal-cancel.flag"), timeout_seconds=60,
    ))
    timeout_control = work / "timeout-control.json"
    timed = render_with_timeout(RenderRequest(
        run_id="timeout", idempotency_key="timeout-v1", input_path=str(deck),
        output_dir=str(work), control_path=str(timeout_control),
        cancel_path=str(work / "timeout-cancel.flag"), timeout_seconds=5, test_hold_seconds=15,
    ))
    owned_pid = int(json.loads(timeout_control.read_text("utf-8"))["pid"])
    orphaned = psutil.pid_exists(owned_pid)
    passed = normal.status == "success" and len(normal.slide_images) == 2 and timed.status == "failed" and not orphaned
    return ProbeResult(
        name="powerpoint-worker",
        status=ProbeStatus.PASS if passed else ProbeStatus.FAIL,
        metrics={"rendered_slides": len(normal.slide_images), "timeout_orphaned": orphaned},
        evidence=normal.slide_images,
    )
```

Execute through `execute_probe` so `artifacts/m0/powerpoint-worker.json` is always written. M0 must prove STA isolation, task-specific output directories, precise PID ownership, heartbeat updates, pre-start cancellation, hard timeout, numeric slide ordering, no orphaned owned process, and no termination of pre-existing PowerPoint instances. Protected-view handling and atomic replacement of final exported `.pptx` remain later production tasks.

- [ ] **Step 9: Commit**

```powershell
git add src/pptmaker/powerpoint src/pptmaker/m0/powerpoint_probe.py tests/powerpoint
git commit -m "feat: validate isolated PowerPoint rendering"
```

### Task 5: Deterministic Geometry Checks

**Files:**
- Create: `src/pptmaker/evaluation/geometry.py`
- Create: `src/pptmaker/m0/geometry_probe.py`
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

Create the evidence runner:

```python
# src/pptmaker/m0/geometry_probe.py
from pptmaker.evaluation.geometry import Box, out_of_bounds, overlap_ratio
from pptmaker.m0.contracts import ProbeResult, ProbeStatus


def run_geometry_probe() -> ProbeResult:
    checks = [
        out_of_bounds(Box(90, 10, 20, 20), Box(0, 0, 100, 100)),
        overlap_ratio(Box(0, 0, 10, 10), Box(5, 0, 10, 10)) == 0.5,
        overlap_ratio(Box(0, 0, 10, 10), Box(10, 0, 10, 10)) == 0.0,
    ]
    return ProbeResult(
        name="geometry-checks",
        status=ProbeStatus.PASS if all(checks) else ProbeStatus.FAIL,
        metrics={"checks": len(checks), "passed": sum(checks)},
    )
```

Run `execute_probe('geometry-checks', run_geometry_probe, Path.cwd())` and verify `artifacts/m0/geometry-checks.json` exists.

Run: `conda run -n AI python -m pytest tests/evaluation/test_geometry.py -v`  
Expected: three passing tests.

```powershell
git add src/pptmaker/evaluation src/pptmaker/m0/geometry_probe.py tests/evaluation
git commit -m "feat: add deterministic geometry probes"
```

### Task 6: Upload and SSRF Security Core

**Files:**
- Create: `src/pptmaker/security/uploads.py`
- Create: `src/pptmaker/security/network.py`
- Create: `src/pptmaker/security/fetcher.py`
- Create: `src/pptmaker/m0/security_probe.py`
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
    max_member_bytes: int = 50 * 1024 * 1024
    max_ratio: float = 200.0
    max_nested_archives: int = 0


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
        unix_mode = member.external_attr >> 16
        is_symlink = (unix_mode & 0o170000) == 0o120000
        if candidate.is_absolute() or ".." in candidate.parts or ":" in member.filename or member.filename.startswith(("\\\\", "//")):
            raise UnsafeArchive("path traversal detected")
        if is_symlink:
            raise UnsafeArchive("symbolic links are forbidden")
        if member.flag_bits & 0x1:
            raise UnsafeArchive("encrypted members are forbidden")
        if member.file_size > limits.max_member_bytes:
            raise UnsafeArchive("single member exceeds limit")
        if candidate.suffix.lower() in {".zip", ".7z", ".rar", ".gz"} and limits.max_nested_archives == 0:
            raise UnsafeArchive("nested archives are forbidden")
        if candidate.suffix.lower() in {".vba", ".bin", ".exe", ".dll", ".js", ".vbs", ".ole"}:
            raise UnsafeArchive("active or embedded content is forbidden")
    compressed = sum(member.compress_size for member in members)
    uncompressed = sum(member.file_size for member in members)
    if uncompressed > limits.max_uncompressed_bytes:
        raise UnsafeArchive("uncompressed size exceeds limit")
    ratio = uncompressed / max(compressed, 1)
    if ratio > limits.max_ratio:
        raise UnsafeArchive("compression ratio exceeds limit")
    return ArchiveInspection(len(members), compressed, uncompressed)


def inspect_office_package(path: Path, limits: ArchiveLimits) -> ArchiveInspection:
    if path.suffix.lower() not in {".docx", ".pptx", ".xlsx"}:
        raise UnsafeArchive("only non-macro OOXML extensions are allowed")
    if path.read_bytes()[:4] != b"PK\x03\x04":
        raise UnsafeArchive("extension does not match ZIP-based OOXML type")
    inspection = inspect_zip(path, limits)
    with ZipFile(path) as archive:
        names = {item.filename.lower() for item in archive.infolist()}
    expected_root = {".docx": "word/", ".pptx": "ppt/", ".xlsx": "xl/"}[path.suffix.lower()]
    if not any(name.startswith(expected_root) for name in names):
        raise UnsafeArchive("extension does not match Office package contents")
    forbidden = ("vbaproject.bin", "/embeddings/", "oleobject", "activex", "externallinks/")
    if any(any(marker in name for marker in forbidden) for name in names):
        raise UnsafeArchive("macro, OLE, ActiveX, embedding, or external link is forbidden")
    return inspection
```

Add tests that build ZIP members for `C:/escape`, `\\server\share`, a Unix symlink via `external_attr`, an encrypted flag, nested ZIP, one oversized member, `ppt/vbaProject.bin`, `ppt/embeddings/oleObject1.bin`, and a DOCX package renamed `.pptx`. Each must raise the exact corresponding `UnsafeArchive` message. Add positive synthetic DOCX and PPTX package tests so rejection rules do not block normal inputs.

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


def test_blocks_ipv4_mapped_ipv6():
    assert is_forbidden_ip("::ffff:127.0.0.1")
```

- [ ] **Step 4: Implement IP classification**

```python
# src/pptmaker/security/network.py
from ipaddress import ip_address


def is_forbidden_ip(value: str) -> bool:
    address = ip_address(value)
    if getattr(address, "ipv4_mapped", None) is not None:
        address = address.ipv4_mapped
    return not address.is_global
```

- [ ] **Step 5: Test complete URL and redirect validation with injected DNS**

```python
# tests/security/test_fetcher.py
import pytest

from pptmaker.security.fetcher import SafeFetchPolicy, UnsafeUrl, validate_target


@pytest.mark.parametrize("url", [
    "file:///C:/secret.txt", "ftp://example.com/a", "http://user:pass@example.com/",
    "http://example.com:22/", "http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/",
])
def test_rejects_unsafe_targets(url: str):
    resolver = lambda host: [host] if host.replace(".", "").isdigit() else ["93.184.216.34"]
    with pytest.raises(UnsafeUrl):
        validate_target(url, resolver, SafeFetchPolicy())


def test_rejects_dns_rebinding_result():
    answers = iter([["93.184.216.34"], ["127.0.0.1"]])
    resolver = lambda host: next(answers)
    with pytest.raises(UnsafeUrl):
        validate_target("https://example.com/", resolver, SafeFetchPolicy())
```

```python
# src/pptmaker/security/fetcher.py
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

from pptmaker.security.network import is_forbidden_ip


class UnsafeUrl(ValueError):
    pass


@dataclass(frozen=True)
class SafeFetchPolicy:
    allowed_ports: tuple[int, ...] = (80, 443)
    max_redirects: int = 5
    max_response_bytes: int = 10 * 1024 * 1024
    timeout_seconds: float = 15.0


def validate_target(url: str, resolver: Callable[[str], list[str]], policy: SafeFetchPolicy) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeUrl("only absolute HTTP(S) URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeUrl("URL credentials are forbidden")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in policy.allowed_ports:
        raise UnsafeUrl("port is forbidden")
    first = set(resolver(parsed.hostname))
    second = set(resolver(parsed.hostname))
    if not first or first != second:
        raise UnsafeUrl("DNS answer is empty or unstable")
    if any(is_forbidden_ip(address) for address in first):
        raise UnsafeUrl("target resolves to a forbidden address")
```

Append the bounded redirect fetcher:

```python
import httpx
from urllib.parse import urljoin


def safe_fetch(url: str, resolver, policy: SafeFetchPolicy, transport=None) -> bytes:
    timeout = httpx.Timeout(policy.timeout_seconds)
    current = url
    with httpx.Client(follow_redirects=False, timeout=timeout, transport=transport) as client:
        for redirect_count in range(policy.max_redirects + 1):
            validate_target(current, resolver, policy)
            with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location or redirect_count == policy.max_redirects:
                        raise UnsafeUrl("redirect limit exceeded")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                chunks, total = [], 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > policy.max_response_bytes:
                        raise UnsafeUrl("response exceeds size limit")
                    chunks.append(chunk)
                return b"".join(chunks)
    raise UnsafeUrl("redirect loop")
```

Add `tests/security/test_fetcher.py` cases using `httpx.MockTransport`: a redirect to `http://169.254.169.254/latest/meta-data/` must raise `UnsafeUrl`; a body larger than `max_response_bytes` must raise; credentials, abnormal ports, and redirect loops must raise; a resolver returning public IPs on the first call and private IPs on the second must raise as unstable DNS. These tests validate policy behavior; M5 must replace the transport with connection pinning so validation and socket connection cannot race.

- [ ] **Step 6: Produce machine-readable security evidence**

```python
# src/pptmaker/m0/security_probe.py
from pathlib import Path
from zipfile import ZipFile

from pptmaker.m0.contracts import ProbeResult, ProbeStatus
from pptmaker.security.fetcher import SafeFetchPolicy, UnsafeUrl, validate_target
from pptmaker.security.uploads import ArchiveLimits, UnsafeArchive, inspect_zip


def run_security_probe(root: Path) -> ProbeResult:
    work = root / "artifacts" / "m0" / "security-probe"
    work.mkdir(parents=True, exist_ok=True)
    bad_zip = work / "traversal.zip"
    with ZipFile(bad_zip, "w") as archive:
        archive.writestr("../escape.txt", "x")
    checks = []
    try:
        inspect_zip(bad_zip, ArchiveLimits())
        checks.append(False)
    except UnsafeArchive:
        checks.append(True)
    try:
        validate_target("http://169.254.169.254/latest/meta-data/", lambda host: [host], SafeFetchPolicy())
        checks.append(False)
    except UnsafeUrl:
        checks.append(True)
    passed = all(checks)
    return ProbeResult(
        name="upload-security", status=ProbeStatus.PASS if passed else ProbeStatus.FAIL,
        metrics={"challenge_checks": len(checks), "passed_checks": sum(checks)},
    )
```

Run it through `execute_probe('upload-security', ...)` and verify `artifacts/m0/upload-security.json` exists.

- [ ] **Step 7: Run tests and commit**

Run: `conda run -n AI python -m pytest tests/security -v`  
Expected: all tests PASS.

```powershell
git add src/pptmaker/security src/pptmaker/m0/security_probe.py tests/security
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


def _request(client: OpenAI, messages: list[dict[str, str]]) -> tuple[str, object]:
    response = client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        temperature=0,
        response_format={"type": "json_object"},
        timeout=30,
        messages=messages,
    )
    return response.choices[0].message.content or "", response.usage


def run_online_probe(iterations: int = 20) -> ProbeResult:
    key = os.environ["DEEPSEEK_API_KEY"]
    client = OpenAI(api_key=key, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    base_messages = [
        {"role": "system", "content": "输出JSON对象，字段为title和slides；slides包含3到12个中文页面标题。"},
        {"role": "user", "content": "为一个中文AI PPT生成器项目生成项目汇报大纲。"},
    ]
    first_pass = repaired = empty = timeouts = rate_limits = 0
    latencies: list[float] = []
    prompt_tokens = completion_tokens = 0
    for _ in range(iterations):
        started = time.perf_counter()
        try:
            raw, usage = _request(client, base_messages)
            latencies.append(time.perf_counter() - started)
            prompt_tokens += int(usage.prompt_tokens if usage else 0)
            completion_tokens += int(usage.completion_tokens if usage else 0)
            if not raw:
                empty += 1
                continue
            try:
                parse_outline(raw)
                first_pass += 1
                repaired += 1
                continue
            except Exception:
                repair_messages = [
                    {"role": "system", "content": "把输入修复为满足title:string和slides:string[3..12]的JSON对象，只输出JSON。"},
                    {"role": "user", "content": raw},
                ]
                fixed, fixed_usage = _request(client, repair_messages)
                prompt_tokens += int(fixed_usage.prompt_tokens if fixed_usage else 0)
                completion_tokens += int(fixed_usage.completion_tokens if fixed_usage else 0)
                parse_outline(fixed)
                repaired += 1
        except Exception as exc:
            name = type(exc).__name__.lower()
            timeouts += int("timeout" in name)
            rate_limits += int("ratelimit" in name or "rate_limit" in name)
    ordered = sorted(latencies)
    p50 = ordered[int((len(ordered) - 1) * 0.50)] if ordered else 0.0
    p95 = ordered[int((len(ordered) - 1) * 0.95)] if ordered else 0.0
    first_rate = first_pass / iterations
    repaired_rate = repaired / iterations
    passed = first_rate >= 0.95 and repaired_rate == 1.0
    return ProbeResult(
        name="deepseek-structured-output",
        status=ProbeStatus.PASS if passed else ProbeStatus.FAIL,
        metrics={
            "iterations": iterations, "first_pass_rate": first_rate,
            "repaired_pass_rate": repaired_rate, "empty_responses": empty,
            "timeouts": timeouts, "rate_limits": rate_limits,
            "p50_seconds": p50, "p95_seconds": p95,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
        },
    )
```

Add these imports to the same module:

```python
from pptmaker.m0.contracts import ProbeResult, ProbeStatus
```

- [ ] **Step 4: Run offline tests**

Run: `conda run -n AI python -m pytest tests/m0/test_deepseek_probe.py -v`  
Expected: two passing tests without requiring a key.

- [ ] **Step 5: Run online probe without exposing the key**

Set `DEEPSEEK_API_KEY` in the current terminal or Windows Credential Manager, then run:

```powershell
conda run -n AI python -c "from pathlib import Path; from pptmaker.m0.artifacts import execute_probe; from pptmaker.m0.deepseek_probe import run_online_probe; root=Path.cwd(); print(execute_probe('deepseek-structured-output', run_online_probe, root))"
```

Expected: 20 requests, first-pass schema rate >=95%, one-repair pass rate 100%, and `artifacts/m0/deepseek-structured-output.json` with latency, token, empty-response, timeout, and rate-limit metrics. No run may use more than one repair call.

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


def parse_pptx(path: Path) -> ParsedDocument:
    from pptx import Presentation

    texts, locations = [], []
    for slide_index, slide in enumerate(Presentation(path).slides, start=1):
        for shape_index, shape in enumerate(slide.shapes, start=1):
            if getattr(shape, "has_text_frame", False) and shape.text.strip():
                texts.append(shape.text.strip())
                locations.append(f"slide:{slide_index}/shape:{shape_index}")
    return ParsedDocument(kind="pptx", text="\n".join(texts), locations=locations)
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

Add this mandatory-core evidence runner to `src/pptmaker/m0/parser_probe.py`:

```python
def run_parser_core_probe(root: Path) -> ProbeResult:
    from tests.fixtures.documents.generate import SENTINEL, generate

    fixture_root = root / "artifacts" / "m0" / "parser-fixtures"
    generate(fixture_root)
    markdown = parse_markdown((fixture_root / "sample.md").read_text("utf-8"))
    powerpoint = parse_pptx(fixture_root / "sample.pptx")
    checks = [SENTINEL in markdown.text, SENTINEL in powerpoint.text, bool(powerpoint.locations)]
    return ProbeResult(
        name="parser-core",
        status=ProbeStatus.PASS if all(checks) else ProbeStatus.FAIL,
        metrics={"required_checks": 3, "passed_checks": sum(checks)},
    )
```

Add imports for `ProbeResult` and `ProbeStatus`, execute through `execute_probe`, and verify `artifacts/m0/parser-core.json` exists. Markdown and PPTX are mandatory. DOCX, PDF, scanned/double-column PDF, notes, grouped shapes, charts, encrypted/corrupt/oversized inputs, code blocks, and complex tables are exploratory matrix rows. `xfail` and empty `locations` never count as PASS; every supported row must assert page, paragraph, slide, or object location.

- [ ] **Step 8: Commit**

```powershell
git add pyproject.toml src/pptmaker/m0/parser_probe.py tests/m0/test_parser_probe.py tests/fixtures/documents docs/evaluations/m0-parser-matrix.md
git commit -m "test: measure document parser capabilities"
```

### Task 9: Vision-Model Benchmark Harness

**Files:**
- Create: `src/pptmaker/m0/vision_schema.py`
- Create: `src/pptmaker/m0/vision_metrics.py`
- Create: `src/pptmaker/m0/vision_adapter.py`
- Create: `src/pptmaker/m0/vision_runner.py`
- Create: `src/pptmaker/m0/vision_report.py`
- Create: `benchmarks/vision/generate_cases.py`
- Create: `benchmarks/vision/m0_manifest.jsonl`
- Create: `benchmarks/vision/README.md`
- Test: `tests/m0/test_vision_metrics.py`
- Test: `tests/m0/test_vision_runner.py`
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

Implement a common adapter, strict JSON parser, batch runner, CUDA measurement, and report generator before loading any model:

```python
# src/pptmaker/m0/vision_adapter.py
from pathlib import Path
from typing import Protocol


class VisionAdapter(Protocol):
    model_id: str

    def review(self, image: Path, prompt: str) -> str: ...


class TransformersPipelineAdapter:
    def __init__(self, model_id: str, trust_remote_code: bool = False, model_kwargs: dict | None = None):
        from transformers import pipeline

        self.model_id = model_id
        self._pipe = pipeline(
            "image-text-to-text", model=model_id, trust_remote_code=trust_remote_code,
            device_map="auto", model_kwargs=model_kwargs or {},
        )

    def review(self, image: Path, prompt: str) -> str:
        from PIL import Image

        picture = Image.open(image).convert("RGB")
        picture.thumbnail((1600, 1600))
        messages = [{"role": "user", "content": [
            {"type": "image", "image": picture}, {"type": "text", "text": prompt},
        ]}]
        output = self._pipe(text=messages, max_new_tokens=512, do_sample=False)
        generated = output[0]["generated_text"]
        return generated[-1]["content"] if isinstance(generated, list) else str(generated)
```

```python
# src/pptmaker/m0/vision_runner.py
import json
import time
from pathlib import Path

import torch

from pptmaker.m0.vision_adapter import VisionAdapter
from pptmaker.m0.vision_schema import VisionReview


PROMPT = """检查这张中文PPT页面。只输出符合给定Schema的JSON；问题类型仅使用overflow、crowded、weak_hierarchy、irrelevant_image、misalignment、inconsistent_style。没有问题时issues为空。"""


def parse_review(raw: str) -> VisionReview:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
    return VisionReview.model_validate_json(cleaned)


def run_manifest(adapter: VisionAdapter, manifest: Path) -> list[dict]:
    records = []
    for line in manifest.read_text("utf-8").splitlines():
        case = json.loads(line)
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        raw = ""
        try:
            raw = adapter.review(Path(case["image"]), PROMPT)
            review = parse_review(raw)
            predicted = sorted({issue.type for issue in review.issues})
            valid, error = True, None
        except Exception as exc:
            predicted, valid, error = [], False, f"{type(exc).__name__}: {exc}"
        records.append({
            "case_id": case["case_id"], "split": case["split"], "expected": case["expected"],
            "predicted": predicted, "json_valid": valid, "error": error, "raw": raw,
            "latency_seconds": time.perf_counter() - started,
            "peak_vram_bytes": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else 0,
        })
    return records
```

```python
# tests/m0/test_vision_runner.py
import json
from pathlib import Path

from pptmaker.m0.vision_runner import run_manifest


class FakeAdapter:
    model_id = "fake"

    def review(self, image: Path, prompt: str) -> str:
        return json.dumps({"slide_id": image.stem, "issues": [], "overall_score": 90})


def test_runner_records_json_validity_and_metrics(tmp_path: Path):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({
        "case_id": "normal", "split": "development",
        "image": str(tmp_path / "normal.png"), "expected": [],
    }), "utf-8")
    records = run_manifest(FakeAdapter(), manifest)
    assert records[0]["json_valid"] is True
    assert records[0]["latency_seconds"] >= 0
```

Add the deterministic report function and test it with fixed records before model execution:

```python
# src/pptmaker/m0/vision_report.py
from statistics import median


def summarize(records: list[dict]) -> dict[str, float | int]:
    tp = fp = fn = 0
    latencies, peaks = [], []
    for record in records:
        expected, predicted = set(record["expected"]), set(record["predicted"])
        tp += len(expected & predicted)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
        latencies.append(float(record["latency_seconds"]))
        peaks.append(int(record["peak_vram_bytes"]))
    ordered = sorted(latencies)
    p95 = ordered[int((len(ordered) - 1) * 0.95)] if ordered else 0.0
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "cases": len(records), "precision": precision, "recall": recall, "f1": f1,
        "false_positive_rate": fp / max(len(records), 1),
        "json_valid_rate": sum(bool(r["json_valid"]) for r in records) / max(len(records), 1),
        "p50_seconds": median(latencies) if latencies else 0.0, "p95_seconds": p95,
        "peak_vram_bytes": max(peaks, default=0),
    }
```

```python
# append to tests/m0/test_vision_runner.py
from pptmaker.m0.vision_report import summarize


def test_report_is_computed_from_records():
    summary = summarize([{
        "expected": ["overflow"], "predicted": ["overflow"], "json_valid": True,
        "latency_seconds": 1.0, "peak_vram_bytes": 1024,
    }])
    assert summary["precision"] == 1.0
    assert summary["recall"] == 1.0
    assert summary["peak_vram_bytes"] == 1024
```

The three PIL cases only validate this harness. Use a staged dataset: 5 PowerPoint-rendered pages for fast load/prompt screening; 20 pages with known defects and normal negatives for admission; expand to 50 pages split into development, validation, and frozen test sets only when candidates are close or thresholds need calibration. The frozen test split is not used for prompt or threshold tuning. Record dataset-generation time separately from inference time.

Run models strictly sequentially with `max_concurrent_models=1`, batch size 1, and identical prompt/schema. After each model, delete the adapter/model, call `gc.collect()` and `torch.cuda.empty_cache()`, then record remaining allocated/reserved memory before loading the next candidate:

- existing `models/QwenQwen3-VL-4B-Instruct` in 4-bit;
- Qwen3-VL-2B-Instruct;
- MiniCPM-V-4.6;
- InternVL3.5-2B.

For each model, record 4-bit weight format, load time, JSON validity, precision, recall, false-positive rate, P50/P95 per-slide latency, total sequential evaluation time, and CUDA peak memory in `docs/evaluations/m0-vision-models.md`. This machine has 8188 MiB physical VRAM; the default budget is 6500 MiB, which is stricter than 85% of physical VRAM. If loading crosses the budget, unload immediately, record BLOCKED, and do not start page evaluation. Measure CPU offload as a separate row. Admission requires recall >=70%, false-positive rate <=20%, and JSON validity >=95%. A model that misses any threshold remains a research preview and is disabled by default. Vision-model selection is exploratory and does not block M1; visual auto-repair remains M7 work.

- [ ] **Step 7: Commit harness and report**

```powershell
git add src/pptmaker/m0/vision_schema.py src/pptmaker/m0/vision_metrics.py src/pptmaker/m0/vision_adapter.py src/pptmaker/m0/vision_runner.py src/pptmaker/m0/vision_report.py tests/m0/test_vision_metrics.py tests/m0/test_vision_runner.py benchmarks/vision docs/evaluations/m0-vision-models.md
git commit -m "test: add PPT vision model benchmark"
```

### Task 10: Search and Image Provider Decision Probe

**Files:**
- Create: `src/pptmaker/research/contracts.py`
- Create: `src/pptmaker/m0/search_runner.py`
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

Implement and unit-test this reproducible runner with fake adapters before making network calls:

```python
# src/pptmaker/m0/search_runner.py
import json
import time
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from pptmaker.research.contracts import SearchResult


class SearchAdapter(Protocol):
    name: str

    def search(self, query: str, limit: int = 5) -> list[SearchResult]: ...


def run_queries(adapter: SearchAdapter, queries: list[str], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for query in queries:
            for attempt in range(3):
                started = time.perf_counter()
                try:
                    results = adapter.search(query, limit=5)
                    urls = [str(item.url) for item in results]
                    record = {
                        "provider": adapter.name, "query": query, "attempt": attempt,
                        "latency_seconds": time.perf_counter() - started,
                        "results": [item.model_dump(mode="json") for item in results],
                        "domains": sorted({urlsplit(url).hostname for url in urls}),
                        "duplicate_urls": len(urls) - len(set(urls)), "error": None,
                    }
                except Exception as exc:
                    record = {
                        "provider": adapter.name, "query": query, "attempt": attempt,
                        "latency_seconds": time.perf_counter() - started,
                        "results": [], "domains": [], "duplicate_urls": 0,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def summarize_records(records: list[dict]) -> dict[str, float | int]:
    latencies = sorted(float(item["latency_seconds"]) for item in records)
    successes = [item for item in records if item["error"] is None]
    return {
        "runs": len(records),
        "error_rate": 1 - len(successes) / max(len(records), 1),
        "p50_seconds": latencies[int((len(latencies) - 1) * 0.5)] if latencies else 0.0,
        "domain_count": len({domain for item in successes for domain in item["domains"]}),
        "duplicate_urls": sum(int(item["duplicate_urls"]) for item in successes),
        "result_count": sum(len(item["results"]) for item in successes),
    }
```

The fake-adapter test returns duplicate results on its first call and raises on its second call. After `run_queries`, parse JSONL and assert that both records remain; call `summarize_records` and assert `runs == 3`, `error_rate > 0`, and `duplicate_urls > 0`. This test makes no network call.

Evaluate at least two keyed search candidates usable from China and at least two image sources with explicit API/license terms. Run these fixed queries exactly: `2025中国生成式AI市场规模 官方数据`, `中国企业数字化转型统计报告`, `人工智能项目实施路线图`, `PowerPoint可访问性规范`, `北京常住人口 官方统计`, `新能源汽车销量 中国汽车工业协会`, `免费可商用 人工智能 办公 图片`, `免费可商用 团队协作 图片`, `科技蓝 抽象背景 免费商用`, `数据分析 图标 免费商用`. Store raw normalized responses, timings, domains, duplicate counts, and errors in JSONL; generate `docs/evaluations/m0-search-and-assets.md` from that evidence, then add human top-five Chinese-relevance scores and terms/license URLs.

The formal M0 path must fail closed when no key is configured. Manual URL ingestion is evaluated separately. No-key scraping is an experimental row and cannot win the default-provider decision.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/research src/pptmaker/m0/search_runner.py tests/research docs/evaluations/m0-search-and-assets.md
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


REQUIRED = (
    "pptx-baseline",
    "powerpoint-worker",
    "geometry-checks",
    "upload-security",
    "deepseek-structured-output",
    "parser-core",
)


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
