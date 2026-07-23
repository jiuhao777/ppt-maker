# M1 Project Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a local Streamlit workspace with restart-safe SQLite projects, JSON portability, secret-safe Provider capability probing, and interrupted LangGraph execution recovery.

**Architecture:** Domain models remain independent from Streamlit. A small SQLite repository is the project system of record, Provider configuration and API Keys remain session-only, and LangGraph uses a separate SQLite checkpoint namespace. The UI calls tested application services and never accesses SQL or SDK clients directly.

**Tech Stack:** Python 3.10.20, Streamlit 1.59.1, Pydantic 2.13.4, OpenAI 2.45.0, LangGraph 1.2.9, SQLite, pytest 9.0.2, Playwright.

## Global Constraints

- Add only `streamlit==1.59.1`, `langgraph==1.2.9`, and the installed compatible `langgraph-checkpoint-sqlite` version to project dependencies and the environment lock.
- Store application data at `%LOCALAPPDATA%\PPTMaker\pptmaker.db`; tests inject temporary database paths.
- Never persist API Keys, Provider response bodies, request headers, SDK exception strings, or absolute local paths.
- Use only `TEST_KEY` and `PLACEHOLDER` in committed code and tests.
- Skip the DeepSeek online test unless `DEEPSEEK_API_KEY` exists in the current process.
- LangSmith tracing is disabled by default.
- JSON imports are limited to 5 MiB, depth 20, 10,000 keys, and 1 MiB per string.
- Implement only M1; do not generate outlines, slides, research, images, or PPTX files.

---

### Task 1: Dependencies and Application Paths

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements/ai-py310-win.lock.txt`
- Create: `src/pptmaker/app_paths.py`
- Test: `tests/test_app_paths.py`

**Interfaces:**
- Produces: `application_data_dir() -> Path`
- Produces: `database_path() -> Path`
- Consumes: optional `PPTMAKER_DATA_DIR` override used only by tests and local development.

- [ ] **Step 1: Write the failing path test**

```python
def test_database_path_uses_injected_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("PPTMAKER_DATA_DIR", str(tmp_path))
    assert database_path() == tmp_path / "pptmaker.db"
```

- [ ] **Step 2: Run the test**

Run: `conda run -n AI python -m pytest tests/test_app_paths.py -v`

Expected: FAIL because `pptmaker.app_paths` does not exist.

- [ ] **Step 3: Implement the path boundary**

```python
def application_data_dir() -> Path:
    override = os.getenv("PPTMAKER_DATA_DIR")
    root = Path(override) if override else Path(os.environ["LOCALAPPDATA"]) / "PPTMaker"
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return application_data_dir() / "pptmaker.db"
```

- [ ] **Step 4: Install and lock dependencies**

Run:

```powershell
conda run -n AI python -m pip install "streamlit==1.59.1" "langgraph==1.2.9" "langgraph-checkpoint-sqlite"
conda run -n AI python -m pip freeze
```

Record the resolved exact checkpoint package version in `pyproject.toml` and
regenerate `requirements/ai-py310-win.lock.txt`.

- [ ] **Step 5: Run the test and dependency check**

Run:

```powershell
conda run -n AI python -m pytest tests/test_app_paths.py -v
conda run -n AI python -m pip check
```

Expected: path test PASS; no dependency conflict introduced by M1. Preserve and
record the pre-existing `datasets 5.0.0` / `fsspec 2026.6.0` warning separately.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml requirements/ai-py310-win.lock.txt src/pptmaker/app_paths.py tests/test_app_paths.py
git commit -m "chore: add M1 runtime foundation"
```

### Task 2: Project Repository and JSON Portability

**Files:**
- Create: `src/pptmaker/projects/models.py`
- Create: `src/pptmaker/projects/repository.py`
- Create: `src/pptmaker/projects/portability.py`
- Create: `src/pptmaker/projects/__init__.py`
- Test: `tests/projects/test_repository.py`
- Test: `tests/projects/test_portability.py`

**Interfaces:**
- Produces: `Project`, `ProjectCreate`, `ProjectUpdate`, `ProjectExport`
- Produces: `ProjectRepository.create/get/list/update/delete`
- Produces: `export_project(project) -> bytes`
- Produces: `import_project(data: bytes, repository) -> Project`

- [ ] **Step 1: Write failing CRUD and restart tests**

```python
def test_project_survives_repository_restart(tmp_path):
    path = tmp_path / "projects.db"
    created = ProjectRepository(path).create(ProjectCreate(name="Demo"))
    reopened = ProjectRepository(path).get(created.id)
    assert reopened.name == "Demo"
    assert reopened.business_state == "DRAFT"
    assert reopened.execution_state == "IDLE"


def test_stale_version_cannot_overwrite_newer_project(repository):
    project = repository.create(ProjectCreate(name="Demo"))
    repository.update(project.id, ProjectUpdate(name="New"), project.version)
    with pytest.raises(VersionConflict):
        repository.update(project.id, ProjectUpdate(name="Old"), project.version)
```

- [ ] **Step 2: Run repository tests**

Run: `conda run -n AI python -m pytest tests/projects/test_repository.py -v`

Expected: FAIL because project models and repository do not exist.

- [ ] **Step 3: Implement models and repository**

Use UUID strings, UTC timestamps, a JSON payload column, and integer optimistic
version. Initialize one `projects` table with parameterized SQL. Every mutation
uses `with connection:` and verifies affected row count. `delete` requires an
exact project ID.

- [ ] **Step 4: Write failing portability limit tests**

```python
def test_export_never_contains_provider_credentials(project):
    encoded = export_project(project)
    assert b"api_key" not in encoded.lower()
    assert b"TEST_KEY" not in encoded


@pytest.mark.parametrize("payload", [
    nested_json(depth=21),
    json_with_keys(10_001),
    json.dumps({"name": "x" * (1024 * 1024 + 1)}).encode(),
])
def test_import_rejects_resource_abuse(payload, repository):
    with pytest.raises(InvalidProjectImport):
        import_project(payload, repository)
```

- [ ] **Step 5: Implement bounded JSON import/export**

Read at most `5 * 1024 * 1024 + 1` bytes. After `json.loads`, walk the object
iteratively, counting depth, keys, and string lengths before Pydantic
validation. Import assigns a new UUID and persists only the last Provider
preset name.

- [ ] **Step 6: Run project tests**

Run: `conda run -n AI python -m pytest tests/projects -v`

Expected: all project tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/pptmaker/projects tests/projects
git commit -m "feat: persist portable projects"
```

### Task 3: Secret-Safe Logging and Provider Errors

**Files:**
- Create: `src/pptmaker/security/secrets.py`
- Create: `src/pptmaker/logging_config.py`
- Test: `tests/security/test_secret_redaction.py`

**Interfaces:**
- Produces: `redact_text(value: str) -> str`
- Produces: `RedactKeysFilter(logging.Filter)`
- Produces: `configure_logging() -> None`
- Produces: `safe_provider_error(exc: Exception) -> ProviderError`

- [ ] **Step 1: Write failing redaction tests**

```python
@pytest.mark.parametrize("value", [
    "Authorization: Bearer TEST_KEY",
    "Bearer TEST_KEY",
    "api_key=TEST_KEY",
])
def test_log_filter_removes_secrets(value, caplog):
    configure_logging()
    logging.getLogger("pptmaker.test").warning("%s", value)
    assert "TEST_KEY" not in caplog.text


def test_provider_error_never_returns_sdk_text():
    result = safe_provider_error(RuntimeError("https://host key=TEST_KEY body=private"))
    assert result.category == "unknown"
    assert "TEST_KEY" not in result.message
    assert "https://" not in result.message
```

- [ ] **Step 2: Run the tests**

Run: `conda run -n AI python -m pytest tests/security/test_secret_redaction.py -v`

Expected: FAIL because the logging boundary does not exist.

- [ ] **Step 3: Implement one output-layer filter**

Redact `record.msg` and recursively redact string values in `record.args`.
Match case-insensitive `Authorization`, `Bearer`, `api_key`, and `sk-` tokens.
Configure `httpx`, `httpcore`, and `openai` to `WARNING`. Do not add logging
handlers when one is already configured.

- [ ] **Step 4: Implement fixed Provider error categories**

Map SDK exception classes to `authentication`, `rate_limit`, `timeout`,
`network`, `unsupported`, or `unknown`. Return only fixed Chinese user
messages; never include `str(exc)`.

- [ ] **Step 5: Run tests and scan fixtures**

Run:

```powershell
conda run -n AI python -m pytest tests/security/test_secret_redaction.py -v
rg -n "some_secret_key|sk-[A-Za-z0-9_-]{8,}" src tests docs
```

Expected: tests PASS; secret scan returns no committed secret-like fixture.

- [ ] **Step 6: Commit**

```powershell
git add src/pptmaker/security/secrets.py src/pptmaker/logging_config.py tests/security/test_secret_redaction.py
git commit -m "feat: enforce secret-safe logging"
```

### Task 4: Session Provider Configuration and Capability Probe

**Files:**
- Create: `src/pptmaker/providers/models.py`
- Create: `src/pptmaker/providers/presets.py`
- Create: `src/pptmaker/providers/openai_compatible.py`
- Create: `src/pptmaker/providers/__init__.py`
- Test: `tests/providers/test_capabilities.py`
- Test: `tests/providers/test_deepseek_online.py`

**Interfaces:**
- Produces: `ProviderConfig`, `Capability`, `CapabilityReport`
- Produces: `OpenAICompatibleProvider.probe(api_key: str) -> CapabilityReport`
- Produces: preset IDs `deepseek`, `kimi`, `qwen`, `custom`
- Consumes: API Key passed per call and never stored on a persisted model.

- [ ] **Step 1: Write fake-client capability tests**

```python
def test_probe_reports_probed_and_unknown_capabilities(fake_client):
    report = OpenAICompatibleProvider(CONFIG, fake_client).probe("TEST_KEY")
    assert report.status == "success"
    assert report.capabilities["structured_output"].value is True
    assert report.capabilities["structured_output"].source == "probed"
    assert report.capabilities["vision"].value == "unknown"
    assert report.capabilities["max_context"].value == "unknown"


def test_probe_returns_safe_authentication_error(failing_client):
    report = OpenAICompatibleProvider(CONFIG, failing_client).probe("TEST_KEY")
    assert report.status == "failed"
    assert report.error.category == "authentication"
    assert "TEST_KEY" not in report.model_dump_json()
```

- [ ] **Step 2: Run capability tests**

Run: `conda run -n AI python -m pytest tests/providers/test_capabilities.py -v`

Expected: FAIL because the Provider package does not exist.

- [ ] **Step 3: Implement presets and three probes**

Keep API Key as a method argument. Probe basic completion, JSON object output,
and one harmless tool definition with `temperature=0` and short output limits.
Vision and context remain `unknown` unless the selected preset contains
explicit reliable metadata. Claude is not included in the OpenAI-compatible
preset list.

- [ ] **Step 4: Add the explicit online test**

```python
@pytest.mark.online
def test_deepseek_capability_probe():
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        pytest.skip("DEEPSEEK_API_KEY is not configured")
    report = provider_for(DEEPSEEK_PRESET).probe(key)
    assert report.status == "success"
    assert report.capabilities["structured_output"].value is True
```

- [ ] **Step 5: Run offline and optional online tests**

Run:

```powershell
conda run -n AI python -m pytest tests/providers/test_capabilities.py -v
conda run -n AI python -m pytest tests/providers/test_deepseek_online.py -v
```

Expected: offline PASS; online PASS with an environment Key or SKIP without it.

- [ ] **Step 6: Commit**

```powershell
git add src/pptmaker/providers tests/providers
git commit -m "feat: probe model provider capabilities"
```

### Task 5: LangGraph Checkpoint and Interrupted Recovery

**Files:**
- Create: `src/pptmaker/workflow/foundation.py`
- Create: `src/pptmaker/workflow/recovery.py`
- Create: `src/pptmaker/workflow/__init__.py`
- Test: `tests/workflow/test_checkpoint_recovery.py`

**Interfaces:**
- Produces: `build_foundation_graph(checkpointer)`
- Produces: `run_foundation_step(project_id, checkpointer) -> dict`
- Produces: `reconcile_interrupted_projects(repository) -> int`

- [ ] **Step 1: Write restart and interruption tests**

```python
def test_graph_resumes_checkpoint_after_reopen(tmp_path):
    db = tmp_path / "checkpoints.db"
    run_foundation_step("project-1", sqlite_checkpointer(db))
    state = reopened_graph(db).get_state({"configurable": {"thread_id": "project-1"}})
    assert state.values["project_id"] == "project-1"
    assert "api_key" not in state.values


def test_running_project_becomes_recoverable_after_process_death(repository):
    project = repository.create(ProjectCreate(name="Demo"))
    repository.set_execution_state(project.id, "RUNNING")
    assert reconcile_interrupted_projects(repository) == 1
    assert repository.get(project.id).execution_state == "FAILED_RECOVERABLE"
```

- [ ] **Step 2: Run workflow tests**

Run: `conda run -n AI python -m pytest tests/workflow/test_checkpoint_recovery.py -v`

Expected: FAIL because the workflow package does not exist.

- [ ] **Step 3: Implement one deterministic graph node**

The graph state contains only `project_id` and `completed_steps`. Compile with
the SQLite checkpointer. Use `project_id` as `thread_id`. Do not put Provider
config, clients, environment variables, or API Keys in graph state.

- [ ] **Step 4: Implement startup reconciliation**

In one SQLite transaction update every project whose execution state is
`RUNNING` to `FAILED_RECOVERABLE`. Return the affected count. Do not change
`WAITING_FOR_USER`, `PAUSED`, or terminal states.

- [ ] **Step 5: Run workflow and project tests**

Run:
`conda run -n AI python -m pytest tests/workflow tests/projects -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/pptmaker/workflow tests/workflow
git commit -m "feat: recover interrupted workflows"
```

### Task 6: Streamlit Workspace

**Files:**
- Create: `src/pptmaker/ui/app.py`
- Create: `src/pptmaker/ui/state.py`
- Create: `src/pptmaker/ui/__init__.py`
- Create: `.streamlit/config.toml`
- Test: `tests/ui/test_app_smoke.py`
- Test: `tests/ui/test_state.py`
- Test: `tests/ui/test_browser_flow.py`

**Interfaces:**
- Produces: `initialize_session_state()`
- Produces: `main()`
- Consumes: `ProjectRepository`, Provider presets, capability service, and workflow recovery.

**Required skill:** Use `developing-with-streamlit` before implementing this task,
then use `playwright` for the real-browser acceptance step.

- [ ] **Step 1: Write session-state tests**

```python
def test_session_defaults_never_persist_api_key():
    state = {}
    initialize_session_state(state)
    assert state["api_key"] == ""
    assert "api_key" not in ProjectCreate(name="Demo").model_dump()
```

- [ ] **Step 2: Run UI unit tests**

Run: `conda run -n AI python -m pytest tests/ui/test_state.py -v`

Expected: FAIL because the UI state module does not exist.

- [ ] **Step 3: Implement the three minimal views**

Use native Streamlit forms:

- project list/create/import/delete-confirmation;
- global Provider settings with password input and capability test;
- project workspace with export and last preset selection.

Show “任务运行时请勿刷新；刷新后需重新输入 API Key” whenever execution
state is `RUNNING`. Call `configure_logging()` and
`reconcile_interrupted_projects()` once during startup.

- [ ] **Step 4: Add Streamlit smoke test**

Use `streamlit.testing.v1.AppTest` with an injected temporary data directory.
Assert the app starts, displays “PPT Maker”, and renders the API Key password
input without exceptions.

- [ ] **Step 5: Run UI tests**

Run: `conda run -n AI python -m pytest tests/ui -v`

Expected: PASS.

- [ ] **Step 6: Add and run the real-browser critical flow**

Start Streamlit against a temporary `PPTMAKER_DATA_DIR`, then use Playwright to
create a project, enter `TEST_KEY` in the password field, refresh the page,
verify the Key field is empty, export the project, import it, and delete it
through the confirmation control. Save no screenshots or traces containing the
sentinel.

Run: `conda run -n AI python -m pytest tests/ui/test_browser_flow.py -v`

Expected: PASS.

- [ ] **Step 7: Start the app for manual verification**

Run:
`conda run -n AI streamlit run src/pptmaker/ui/app.py`

Verify create, restart recovery, Provider form, export, import, and confirmed
delete. Do not enter a real Key unless testing capability detection.

- [ ] **Step 8: Commit**

```powershell
git add src/pptmaker/ui .streamlit tests/ui
git commit -m "feat: add local project workspace"
```

### Task 7: M1 Harness and Acceptance Report

**Files:**
- Create: `scripts/check_m1_gate.py`
- Create: `tests/scripts/test_check_m1_gate.py`
- Create: `artifacts/m1/restart-recovery.json`
- Create: `artifacts/m1/provider-capabilities.json`
- Create: `docs/evaluations/m1-gate-report.md`
- Modify: `PPT agent.md`

**Interfaces:**
- Consumes: JUnit result, temporary secret-scan fixtures, and M1 acceptance checks.
- Produces: nonzero exit for test failures, secret leakage, missing restart evidence, or missing capability evidence.

- [ ] **Step 1: Write gate failure tests**

```python
def test_gate_rejects_secret_in_export(tmp_path):
    (tmp_path / "project.json").write_text('{"api_key":"TEST_KEY"}', "utf-8")
    assert check_m1_gate(tmp_path) == ["secret leakage: project.json"]
```

- [ ] **Step 2: Implement the minimal gate**

Check the JUnit summary has zero failures/errors, scan generated SQLite/JSON/log
and checkpoint files for the runtime test sentinel supplied by the test, and
require schema-valid `artifacts/m1/restart-recovery.json` and
`artifacts/m1/provider-capabilities.json`.

- [ ] **Step 3: Run the complete suite**

Run:

```powershell
conda run -n AI python -m pytest -v --basetemp=artifacts/pytest-m1 --junitxml=artifacts/m1/pytest.xml
conda run -n AI python scripts/check_m1_gate.py
```

Expected: all tests PASS; M1 gate exits 0.

- [ ] **Step 4: Write the evidence-based report**

Record dependency versions, CRUD/restart results, JSON limits, secret scan,
Provider capability results, interrupted recovery, Streamlit smoke result,
known limitations, and exact M2 entry criteria. Mark the explicit online
DeepSeek result PASS or SKIP according to whether the environment Key was set.

- [ ] **Step 5: Update the roadmap and run final checks**

Mark M1 complete in `PPT agent.md` only after automated and user UI acceptance.

Run:

```powershell
git diff --check
git status --short
conda run -n AI python scripts/check_m1_gate.py
```

- [ ] **Step 6: Commit**

```powershell
git add scripts/check_m1_gate.py tests/scripts/test_check_m1_gate.py docs/evaluations/m1-gate-report.md "PPT agent.md"
git commit -m "docs: complete M1 project foundation gate"
```
