# M2 Requirements Interview and Outline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a restart-safe Agent workflow that extracts requirements from user text and supported files, asks only necessary questions, creates editable versioned outlines, and produces research tasks after explicit approval.

**Architecture:** Domain contracts and deterministic decision rules stay independent from Streamlit and LangGraph. SQLite repositories store normalized M2 records, an OpenAI-compatible JSON client supplies validated model results, and a small LangGraph coordinates the application services with project-scoped checkpoints. The UI only calls these tested services.

**Tech Stack:** Python 3.10.20, Pydantic 2.13.4, SQLite, LangGraph 1.2.9, OpenAI 2.45.0, MarkItDown 0.1.5, Streamlit 1.59.1, pytest 9.0.2.

## Global Constraints

- Implement only M2: no web search, Fact Store, OCR, detailed page copy, SlideDSL, PPTX generation, or multi-Agent autonomy.
- Support natural-language text, Markdown, DOCX, text PDF, and PPTX; clearly reject images and scanned PDFs as unrecognized.
- Run every uploaded file through existing M0 upload safety checks before parsing.
- Ask at most one question per turn and never repeat information already established by material or conversation.
- Every blocking question offers “不知道/不确定” and can create an explicitly unverified assumption.
- A model result gets one Schema-repair request; a second failure becomes `FAILED_RECOVERABLE`.
- API Keys remain method arguments and Streamlit session values only; never persist them in SQLite, checkpoints, JSON exports, logs, or LangSmith.
- `WAITING_FOR_USER` holds no execution lease, Worker, or model connection and remains resumable without a 24-hour failure transition.
- Every core contract carries `schema_version=1`.
- Use TDD, minimal code, and one focused commit per task.

---

## File Map

- `src/pptmaker/m2/models.py`: M2 Pydantic contracts and enums.
- `src/pptmaker/m2/repository.py`: SQLite persistence and outline version transitions.
- `src/pptmaker/m2/materials.py`: safe material ingestion and normalized source locations.
- `src/pptmaker/providers/structured.py`: one secret-safe structured JSON request boundary.
- `src/pptmaker/m2/interview.py`: deterministic gap ranking and single-question planning.
- `src/pptmaker/m2/outlines.py`: outline generation, reflection checks, diffs, and research-task derivation.
- `src/pptmaker/m2/workflow.py`: LangGraph routing and checkpoint-safe state.
- `src/pptmaker/ui/m2_workspace.py`: M2 Streamlit panels and handlers.
- `scripts/check_m2_gate.py`: machine-readable M2 acceptance gate.

### Task 1: M2 Domain Contracts

**Files:**
- Create: `src/pptmaker/m2/__init__.py`
- Create: `src/pptmaker/m2/models.py`
- Test: `tests/m2/test_models.py`

**Interfaces:**
- Produces: `RequirementBrief`, `RequirementField`, `ConversationTurn`, `MaterialChunk`, `MaterialIngestResult`, `OutlineGap`, `OutlinePage`, `DeckOutlineDraft`, `DeckOutline`, `ResearchTask`, `GapCandidate`, `InterviewQuestion`, `ReflectionResult`, and `OutlineDiff`.
- Produces: `BusinessState`, `OutlineStatus`, `MaterialStatus`, and `ResearchMaterialType`.

- [ ] **Step 1: Write failing contract tests**

```python
from pydantic import ValidationError

from pptmaker.m2.models import (
    DeckOutline,
    InterviewQuestion,
    OutlinePage,
    ResearchTask,
    RequirementBrief,
)


def test_core_contracts_have_schema_version_one():
    assert RequirementBrief(project_id="p1").schema_version == 1
    assert DeckOutline(
        project_id="p1",
        version=1,
        status="DRAFT",
        narrative="Main story",
        target_slides=1,
        pages=[OutlinePage(order=1, section="Intro", title="Why", objective="Frame")],
    ).schema_version == 1
    assert ResearchTask(
        project_id="p1",
        outline_version=1,
        question="What is the market size?",
        page_id="page-1",
        material_type="data",
        priority="high",
    ).schema_version == 1


def test_interview_question_requires_reason_and_unknown_path():
    with pytest.raises(ValidationError):
        InterviewQuestion(field="audience", text="Who?", reason="")
```

- [ ] **Step 2: Run the focused test**

Run: `conda run -n AI python -m pytest tests/m2/test_models.py -v`

Expected: FAIL because `pptmaker.m2` does not exist.

- [ ] **Step 3: Implement the minimal contracts**

```python
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

BusinessState = Literal[
    "COLLECTING_REQUIREMENTS",
    "WAITING_FOR_USER",
    "GENERATING_OUTLINE",
    "OUTLINE_REVIEW",
    "OUTLINE_APPROVED",
    "FAILED_RECOVERABLE",
    "FAILED_FINAL",
]
OutlineStatus = Literal["DRAFT", "APPROVED", "SUPERSEDED"]


class RequirementField(BaseModel):
    value: str | int | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    source: str | None = None
    assumed: bool = False


class RequirementBrief(BaseModel):
    schema_version: Literal[1] = 1
    project_id: str
    purpose: RequirementField = Field(default_factory=RequirementField)
    audience: RequirementField = Field(default_factory=RequirementField)
    scenario: RequirementField = Field(default_factory=RequirementField)
    duration_minutes: RequirementField = Field(default_factory=RequirementField)
    target_slides: RequirementField = Field(default_factory=RequirementField)
    language: RequirementField = Field(default_factory=RequirementField)
    style: RequirementField = Field(default_factory=RequirementField)
    priorities: RequirementField = Field(default_factory=RequirementField)
    source_boundary: RequirementField = Field(default_factory=RequirementField)
    quality_preference: RequirementField = Field(default_factory=RequirementField)


class InterviewQuestion(BaseModel):
    field: str
    text: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=300)
    allow_unknown: Literal[True] = True


class ConversationTurn(BaseModel):
    role: Literal["user", "agent"]
    content: str = Field(min_length=1, max_length=20_000)
    field: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MaterialChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    source_name: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=1_000_000)


class MaterialIngestResult(BaseModel):
    status: Literal["parsed", "unrecognized", "rejected", "failed"]
    chunks: list[MaterialChunk] = Field(default_factory=list)
    warning: str | None = Field(default=None, max_length=500)


class GapCandidate(BaseModel):
    field: str
    score: float
    blocking: bool


class OutlineGap(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    material_type: Literal["fact", "data", "case", "image", "quote"]
    priority: Literal["high", "medium", "low"]
    search_hint: str = Field(default="", max_length=500)


class OutlinePage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    order: int = Field(ge=1)
    section: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=500)
    key_points: list[str] = Field(default_factory=list, max_length=10)
    page_type: str = Field(default="content", max_length=100)
    source_locations: list[str] = Field(default_factory=list, max_length=100)
    gaps: list[OutlineGap] = Field(default_factory=list, max_length=20)


class DeckOutlineDraft(BaseModel):
    narrative: str = Field(min_length=1, max_length=2_000)
    target_slides: int = Field(ge=1, le=100)
    pages: list[OutlinePage] = Field(min_length=1, max_length=100)


class DeckOutline(DeckOutlineDraft):
    schema_version: Literal[1] = 1
    project_id: str
    version: int = Field(ge=1)
    status: OutlineStatus
    parent_version: int | None = Field(default=None, ge=1)


class ResearchTask(BaseModel):
    schema_version: Literal[1] = 1
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    outline_version: int = Field(ge=1)
    question: str = Field(min_length=1, max_length=500)
    page_id: str
    material_type: Literal["fact", "data", "case", "image", "quote"]
    priority: Literal["high", "medium", "low"]
    search_hint: str = Field(default="", max_length=500)
    status: Literal["pending"] = "pending"


class ReflectionResult(BaseModel):
    passed: bool
    defects: list[str] = Field(default_factory=list)


class OutlineDiff(BaseModel):
    added_page_ids: list[str] = Field(default_factory=list)
    deleted_page_ids: list[str] = Field(default_factory=list)
    moved_page_ids: list[str] = Field(default_factory=list)
    title_changes: dict[str, tuple[str, str]] = Field(default_factory=dict)
```

Do not place API/provider fields on any M2 model.

- [ ] **Step 4: Run contract tests**

Run: `conda run -n AI python -m pytest tests/m2/test_models.py -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/m2 tests/m2/test_models.py
git commit -m "feat: define M2 domain contracts"
```

### Task 2: M2 SQLite Repository and Version State Machine

**Files:**
- Create: `src/pptmaker/m2/repository.py`
- Modify: `src/pptmaker/projects/models.py`
- Modify: `src/pptmaker/projects/portability.py`
- Test: `tests/m2/test_repository.py`
- Test: `tests/projects/test_repository.py`
- Test: `tests/projects/test_portability.py`

**Interfaces:**
- Consumes: models from Task 1 and the same database path used by `ProjectRepository`.
- Produces: `M2Repository.save_brief/get_brief/add_turn/list_turns/save_chunks/list_chunks`.
- Produces: `M2Repository.create_outline/get_outline/list_outlines/update_outline/approve_outline/restore_outline`.
- Produces: `M2Repository.replace_research_tasks/list_research_tasks`.
- Produces: project `business_state` support for every M2 state in Task 1.

- [ ] **Step 1: Write failing persistence and state-transition tests**

```python
def test_approving_new_draft_supersedes_previous_approval(repository):
    first = repository.create_outline(outline(project_id="p1"))
    approved = repository.approve_outline("p1", first.version)
    second = repository.update_outline(approved, pages=[page(title="Updated")])
    repository.approve_outline("p1", second.version)

    versions = {item.version: item.status for item in repository.list_outlines("p1")}
    assert versions == {1: "SUPERSEDED", 2: "APPROVED"}


def test_restoring_history_creates_new_draft(repository):
    original = repository.create_outline(outline(project_id="p1"))
    repository.update_outline(original, pages=[page(title="Changed")])
    restored = repository.restore_outline("p1", original.version)
    assert restored.version == 3
    assert restored.parent_version == 1
    assert restored.status == "DRAFT"


def test_project_accepts_m2_business_state(project_repository):
    project = project_repository.create(ProjectCreate(name="Demo"))
    updated = project_repository.update(
        project.id,
        ProjectUpdate(business_state="WAITING_FOR_USER"),
        expected_version=project.version,
    )
    assert updated.business_state == "WAITING_FOR_USER"
```

- [ ] **Step 2: Run repository tests**

Run: `conda run -n AI python -m pytest tests/m2/test_repository.py -v`

Expected: FAIL because `M2Repository` does not exist.

- [ ] **Step 3: Extend the project business-state contract**

Replace the project-only `Literal["DRAFT"]` type with the shared M2 `BusinessState` plus the existing initial `DRAFT` value:

```python
ProjectBusinessState = Literal[
    "DRAFT",
    "COLLECTING_REQUIREMENTS",
    "WAITING_FOR_USER",
    "GENERATING_OUTLINE",
    "OUTLINE_REVIEW",
    "OUTLINE_APPROVED",
    "FAILED_RECOVERABLE",
    "FAILED_FINAL",
]
```

Add `business_state: ProjectBusinessState | None` to `ProjectUpdate`; keep `ProjectCreate` defaulting to `DRAFT`. JSON import/export accepts only this closed set and preserves it.

- [ ] **Step 4: Create the M2 tables**

Use one initialization transaction and these focused tables:

```sql
CREATE TABLE IF NOT EXISTS m2_briefs (
  project_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS m2_turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS m2_materials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS m2_outlines (
  project_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  status TEXT NOT NULL,
  payload TEXT NOT NULL,
  PRIMARY KEY (project_id, version)
);
CREATE TABLE IF NOT EXISTS m2_research_tasks (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  outline_version INTEGER NOT NULL,
  payload TEXT NOT NULL
);
```

- [ ] **Step 5: Implement atomic outline transitions**

Within `BEGIN IMMEDIATE`, calculate `MAX(version)+1`. Approval must update the selected draft to `APPROVED` and any existing approved version to `SUPERSEDED` in the same transaction. Restoring copies payload into a new `DRAFT`; it never edits history.

- [ ] **Step 6: Run repository and M1 regression tests**

Run:

```powershell
conda run -n AI python -m pytest tests/m2/test_repository.py tests/projects -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/pptmaker/m2/repository.py src/pptmaker/projects/models.py src/pptmaker/projects/portability.py tests/m2/test_repository.py tests/projects
git commit -m "feat: persist M2 workflow versions"
```

### Task 3: Safe Material Ingestion

**Files:**
- Create: `src/pptmaker/m2/materials.py`
- Test: `tests/m2/test_materials.py`
- Reuse: `src/pptmaker/security/uploads.py`
- Reuse: `src/pptmaker/m0/parser_probe.py`

**Interfaces:**
- Produces: `ingest_material(project_id: str, filename: str, content: bytes) -> MaterialIngestResult`.
- Consumes: `ArchiveLimits`, `inspect_office_package`, `parse_markdown`, `parse_pptx`, and `parse_with_markitdown`.
- Guarantees: task-local temporary directory cleanup on success and exception.

- [ ] **Step 1: Write failing format and cleanup tests**

```python
@pytest.mark.parametrize("name", ["sample.md", "sample.docx", "sample.pdf", "sample.pptx"])
def test_supported_material_produces_located_chunks(name, fixtures):
    result = ingest_material("p1", name, fixtures[name])
    assert result.status == "parsed"
    assert result.chunks
    assert all(chunk.source_name == name for chunk in result.chunks)


@pytest.mark.parametrize("name", ["image.png", "scan.pdf"])
def test_unrecognized_visual_material_is_explicit(name, fixtures):
    result = ingest_material("p1", name, fixtures[name])
    assert result.status == "unrecognized"
    assert result.warning == "图片或扫描型 PDF 暂未识别"


def test_task_temp_directory_is_removed_after_parser_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(materials, "temporary_root", lambda: tmp_path)
    monkeypatch.setattr(materials, "parse_with_markitdown", raising_parser)
    ingest_material("p1", "broken.pdf", b"%PDF-1.7")
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 2: Run material tests**

Run: `conda run -n AI python -m pytest tests/m2/test_materials.py -v`

Expected: FAIL because the ingestion module does not exist.

- [ ] **Step 3: Implement explicit dispatch**

```python
SUPPORTED = {".md", ".docx", ".pdf", ".pptx"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def ingest_material(project_id: str, filename: str, content: bytes) -> MaterialIngestResult:
    suffix = Path(filename).suffix.lower()
    if len(content) > MAX_UPLOAD_BYTES:
        return MaterialIngestResult(status="rejected", warning="文件超过 50 MiB 限制")
    if suffix not in SUPPORTED:
        return MaterialIngestResult(status="unrecognized", warning="图片或扫描型 PDF 暂未识别")
    with TemporaryDirectory(prefix="pptmaker-m2-", dir=temporary_root()) as folder:
        path = Path(folder) / Path(filename).name
        path.write_bytes(content)
        if suffix in {".docx", ".pptx"}:
            inspect_office_package(path, ArchiveLimits())
        parsed = parse_markdown(content.decode("utf-8")) if suffix == ".md" else (
            parse_pptx(path) if suffix == ".pptx" else parse_with_markitdown(path)
        )
        if not parsed.text.strip():
            return MaterialIngestResult(
                status="unrecognized",
                warning="图片或扫描型 PDF 暂未识别",
            )
        return chunks_from_parsed(project_id, filename, parsed)
```

`chunks_from_parsed` splits non-empty text paragraphs into bounded chunks and maps `parsed.locations[index]` when present, otherwise uses `document`. Catch only expected decoding, parser, archive, and I/O exceptions and return `MaterialIngestResult(status="failed", warning="文件解析失败")`. Never expose `str(exc)` to UI or logs.

- [ ] **Step 4: Run material and security regressions**

Run:

```powershell
conda run -n AI python -m pytest tests/m2/test_materials.py tests/security/test_uploads.py tests/m0/test_parser_probe.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/m2/materials.py tests/m2/test_materials.py
git commit -m "feat: ingest safe M2 materials"
```

### Task 4: Structured Model Request Boundary

**Files:**
- Create: `src/pptmaker/providers/structured.py`
- Test: `tests/providers/test_structured.py`

**Interfaces:**
- Produces: `StructuredModel.generate(schema: type[T], system: str, user: str, api_key: str) -> T`.
- Consumes: `ProviderConfig` and an injected OpenAI client factory.
- Raises: `StructuredOutputError` with fixed categories only.

- [ ] **Step 1: Write failing first-pass, repair, and secret tests**

```python
class Answer(BaseModel):
    value: str


def test_valid_json_needs_one_request(fake_client):
    model = StructuredModel(CONFIG, fake_client)
    assert model.generate(Answer, "system", "user", "TEST_KEY").value == "ok"
    assert fake_client.calls == 1


def test_invalid_json_gets_exactly_one_repair(repairing_client):
    model = StructuredModel(CONFIG, repairing_client)
    assert model.generate(Answer, "system", "user", "TEST_KEY").value == "fixed"
    assert repairing_client.calls == 2


def test_second_invalid_result_returns_safe_error(failing_client):
    with pytest.raises(StructuredOutputError) as error:
        StructuredModel(CONFIG, failing_client).generate(
            Answer, "system", "user", "TEST_KEY"
        )
    assert error.value.category == "invalid_structure"
    assert "TEST_KEY" not in str(error.value)
```

- [ ] **Step 2: Run structured client tests**

Run: `conda run -n AI python -m pytest tests/providers/test_structured.py -v`

Expected: FAIL because `StructuredModel` does not exist.

- [ ] **Step 3: Implement one request and one repair**

Use `response_format={"type": "json_object"}`, `temperature=0`, and the selected model. The repair request contains the validation error summary and original model output but no API Key. Parse with `schema.model_validate_json`. Map SDK failures through `safe_provider_error`; never store request/response content.

```python
class StructuredOutputError(RuntimeError):
    def __init__(self, category: str):
        self.category = category
        super().__init__("模型未返回有效的结构化结果")


for attempt in range(2):
    response = client.chat.completions.create(**request)
    try:
        return schema.model_validate_json(response.choices[0].message.content)
    except ValidationError as exc:
        if attempt == 1:
            raise StructuredOutputError("invalid_structure") from None
        request["messages"].append({
            "role": "user",
            "content": repair_prompt(exc.errors(include_url=False)),
        })
raise AssertionError("unreachable")
```

- [ ] **Step 4: Run provider and redaction tests**

Run:

```powershell
conda run -n AI python -m pytest tests/providers tests/security/test_secret_redaction.py -m "not online" -v
```

Expected: all offline tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/providers/structured.py tests/providers/test_structured.py
git commit -m "feat: add structured model boundary"
```

### Task 5: Requirement Extraction and Interview Planning

**Files:**
- Create: `src/pptmaker/m2/interview.py`
- Test: `tests/m2/test_interview.py`

**Interfaces:**
- Consumes: `StructuredModel`, `RequirementBrief`, `MaterialChunk`, and prior `ConversationTurn` values.
- Produces: `extract_requirements(...) -> RequirementBrief`.
- Produces: `rank_gaps(brief: RequirementBrief) -> list[GapCandidate]`.
- Produces: `plan_next_question(brief: RequirementBrief) -> InterviewQuestion | None`.
- Produces: `accept_unknown(brief, field, assumption) -> RequirementBrief`.

- [ ] **Step 1: Write failing deterministic planner tests**

```python
def test_known_information_is_not_asked_again():
    brief = complete_brief(audience=field("Executives", confidence=0.95))
    brief.scenario = empty_field()
    question = plan_next_question(brief)
    assert question.field == "scenario"
    assert question.field != "audience"


def test_one_call_returns_at_most_one_question():
    brief = RequirementBrief(project_id="p1")
    assert isinstance(plan_next_question(brief), InterviewQuestion)


def test_unknown_answer_creates_marked_assumption():
    updated = accept_unknown(
        RequirementBrief(project_id="p1"),
        "audience",
        "暂按部门管理者作为主要受众，后续验证",
    )
    assert updated.audience.assumed is True
    assert updated.audience.confidence < 0.5
```

- [ ] **Step 2: Run interview tests**

Run: `conda run -n AI python -m pytest tests/m2/test_interview.py -v`

Expected: FAIL because the interview service does not exist.

- [ ] **Step 3: Implement transparent gap scoring**

```python
DEFAULT_PRIORITY = {
    "scenario": 40,
    "audience": 30,
    "priorities": 20,
    "style": 10,
}


def gap_score(field_name: str, value: RequirementField) -> float:
    blocking = 100 if field_name in BLOCKING_FIELDS else 0
    uncertainty = (1 - value.confidence) * 20
    return blocking + DEFAULT_PRIORITY.get(field_name, 0) + uncertainty
```

Sort descending and build one question with a field-specific text and reason. If no blocking gaps remain, return `None`. Extraction uses `StructuredModel` and a prompt that requires source labels and forbids unsupported facts.

- [ ] **Step 4: Add extraction merge tests**

Verify a new extraction cannot overwrite a user-confirmed field with lower-confidence model content. A user correction always wins and carries `source="user"`, `confidence=1.0`.

- [ ] **Step 5: Run M2 service tests**

Run: `conda run -n AI python -m pytest tests/m2/test_interview.py tests/m2/test_models.py -v`

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/pptmaker/m2/interview.py tests/m2/test_interview.py
git commit -m "feat: plan focused requirement interviews"
```

### Task 6: Outline Generation, Reflection, Diff, and Research Tasks

**Files:**
- Create: `src/pptmaker/m2/outlines.py`
- Test: `tests/m2/test_outlines.py`

**Interfaces:**
- Produces: `generate_outline(brief, chunks, model, api_key) -> DeckOutline`.
- Produces: `reflect_outline(brief, outline) -> ReflectionResult`.
- Produces: `diff_outlines(old, new) -> OutlineDiff`.
- Produces: `build_research_tasks(outline) -> list[ResearchTask]`.

- [ ] **Step 1: Write failing deterministic quality tests**

```python
def test_reflection_detects_duplicate_pages_and_duration_mismatch():
    brief = brief_with(duration_minutes=5, target_slides=3)
    outline = deck("Same", "Same", "Different", target_slides=3)
    result = reflect_outline(brief, outline)
    assert "duplicate_titles" in result.defects
    assert result.passed is False


def test_every_unresolved_gap_becomes_research_task():
    outline = deck_with_gaps(
        ("page-1", "Need current market size", "data"),
        ("page-2", "Need product image", "image"),
    )
    tasks = build_research_tasks(outline)
    assert {(task.page_id, task.material_type) for task in tasks} == {
        ("page-1", "data"),
        ("page-2", "image"),
    }


def test_diff_reports_page_add_delete_move_and_title_change():
    diff = diff_outlines(old_outline(), changed_outline())
    assert diff.added_page_ids == ["p3"]
    assert diff.moved_page_ids == ["p2"]
    assert diff.title_changes["p1"] == ("Old", "New")
```

- [ ] **Step 2: Run outline tests**

Run: `conda run -n AI python -m pytest tests/m2/test_outlines.py -v`

Expected: FAIL because the outline service does not exist.

- [ ] **Step 3: Implement generation and bounded reflection**

The generation schema is `DeckOutlineDraft` without repository version fields. Convert it to a version-1 `DeckOutline`. Reflection checks deterministic page count, duplicate normalized titles, empty objectives, missing priorities, unsupported factual language on pages without sources, and gaps without material type. It returns defects and one corrected draft at most; it cannot add goals absent from `RequirementBrief`.

- [ ] **Step 4: Implement stable-ID diff and task derivation**

```python
def build_research_tasks(outline: DeckOutline) -> list[ResearchTask]:
    return [
        ResearchTask(
            project_id=outline.project_id,
            outline_version=outline.version,
            question=gap.question,
            page_id=page.id,
            material_type=gap.material_type,
            priority=gap.priority,
            search_hint=gap.search_hint,
        )
        for page in outline.pages
        for gap in page.gaps
    ]
```

Diff by stable page ID, not by title or position.

- [ ] **Step 5: Run outline, interview, and repository tests**

Run:

```powershell
conda run -n AI python -m pytest tests/m2/test_outlines.py tests/m2/test_interview.py tests/m2/test_repository.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/pptmaker/m2/outlines.py tests/m2/test_outlines.py
git commit -m "feat: generate and review M2 outlines"
```

### Task 7: LangGraph Workflow and Restart Recovery

**Files:**
- Create: `src/pptmaker/m2/workflow.py`
- Test: `tests/m2/test_workflow.py`
- Test: `tests/m2/interrupted_worker.py`

**Interfaces:**
- Produces: `M2GraphState` containing IDs, state labels, and counters only.
- Produces: `build_m2_graph(services, checkpointer)`.
- Produces: `start_or_resume(project_id, api_key, services, checkpointer) -> M2GraphState`.
- Consumes: repositories and services from Tasks 2–6.

- [ ] **Step 1: Write failing routing and secret tests**

```python
def test_graph_pauses_after_one_question(graph, config):
    state = graph.invoke(initial_state("p1"), config)
    assert state["business_state"] == "WAITING_FOR_USER"
    assert state["question_count"] == 1


def test_checkpoint_contains_no_api_key(graph, checkpointer, config):
    graph.invoke(initial_state("p1"), config, context={"api_key": "TEST_KEY"})
    snapshot = graph.get_state(config)
    assert "api_key" not in snapshot.values
    assert "TEST_KEY" not in json.dumps(snapshot.values)


def test_unapproved_outline_cannot_route_to_research(graph, config):
    state = graph.invoke(outline_review_state("p1"), config)
    assert state["business_state"] == "OUTLINE_REVIEW"
    assert state["research_task_count"] == 0
```

- [ ] **Step 2: Run workflow tests**

Run: `conda run -n AI python -m pytest tests/m2/test_workflow.py -v`

Expected: FAIL because the graph does not exist.

- [ ] **Step 3: Implement the smallest state graph**

Nodes call `extract_requirements`, `plan_next_question`, `generate_outline`, and `build_research_tasks`. Use LangGraph `interrupt` before user input and approval. The graph state stores only project ID, business state, current outline version, question count, and research task count. Pass API Key through non-persisted runtime context.

```python
class M2GraphState(TypedDict):
    project_id: str
    business_state: BusinessState
    current_outline_version: int | None
    question_count: int
    research_task_count: int
```

- [ ] **Step 4: Add real interruption recovery test**

The child process marks the project `RUNNING`, starts an M2 invocation, prints only the project ID, and blocks before checkpoint completion. The parent terminates it, reopens both repositories, calls existing startup reconciliation, and verifies:

```python
assert project.execution_state == "FAILED_RECOVERABLE"
assert repository.get_brief(project.id) is not None
    assert b"TEST_KEY" not in checkpoint_database.read_bytes()
```

- [ ] **Step 5: Run workflow and M1 recovery regressions**

Run:

```powershell
conda run -n AI python -m pytest tests/m2/test_workflow.py tests/workflow -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/pptmaker/m2/workflow.py tests/m2/test_workflow.py tests/m2/interrupted_worker.py
git commit -m "feat: orchestrate restart-safe M2 workflow"
```

### Task 8: Streamlit M2 Workspace

**Files:**
- Create: `src/pptmaker/ui/m2_workspace.py`
- Modify: `src/pptmaker/ui/app.py`
- Modify: `src/pptmaker/ui/state.py`
- Test: `tests/ui/test_m2_workspace.py`
- Test: `tests/ui/test_m2_browser_flow.py`

**Interfaces:**
- Produces: `render_m2_workspace(project, repositories, services) -> None`.
- Consumes: session-only `api_key`, M2 repositories, graph commands, and outline services.

**Required skills:** Use `developing-with-streamlit` before implementing this task and `playwright` for the browser acceptance step.

- [ ] **Step 1: Write failing UI smoke tests**

```python
def test_interview_shows_reason_summary_and_unknown_option(app_with_question):
    app = app_with_question.run()
    assert any("为了确定" in item.value for item in app.caption)
    assert any(item.label == "不知道/不确定" for item in app.button)
    assert any("已确认信息" in item.value for item in app.subheader)


def test_outline_approval_names_exact_version(app_with_outline):
    app = app_with_outline.run()
    assert any(item.label == "批准大纲 v1" for item in app.button)
```

- [ ] **Step 2: Run UI tests**

Run: `conda run -n AI python -m pytest tests/ui/test_m2_workspace.py -v`

Expected: FAIL because the M2 workspace does not exist.

- [ ] **Step 3: Implement three focused panels**

Use native Streamlit controls only:

- task description and multi-file uploader;
- one-question interview with reason, progress, confirmed-summary editor, answer, and unknown action;
- outline editor with page add/delete/order fields, version selector, diff summary, restore, save, and exact-version approval.

Use callbacks for actions that change widget-backed session state. If the current project is `WAITING_FOR_USER`, show “继续访谈” and last activity time. Do not render raw model exceptions or material bodies.

- [ ] **Step 4: Integrate without enlarging the existing project controls**

Call `render_m2_workspace` after the selected project’s M1 settings. Keep Provider configuration global and session-only. Normalize only the user-facing strings touched by this integration; do not refactor unrelated M1 controls.

- [ ] **Step 5: Run Streamlit tests**

Run:

```powershell
conda run -n AI python -m pytest tests/ui/test_m2_workspace.py tests/ui/test_app_smoke.py tests/ui/test_state.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run the browser critical path**

With a fake structured model service, automate:

1. create project;
2. enter topic and upload one Markdown file;
3. answer one question using “不知道/不确定”;
4. generate outline;
5. edit and save v2;
6. compare v1/v2;
7. approve v2;
8. refresh and verify v2 and research tasks remain while API Key is empty.

Run: `conda run -n AI python -m pytest tests/ui/test_m2_browser_flow.py -v`

Expected: PASS without network and without saving screenshots/traces containing sentinel keys.

- [ ] **Step 7: Commit**

```powershell
git add src/pptmaker/ui/m2_workspace.py src/pptmaker/ui/app.py src/pptmaker/ui/state.py tests/ui/test_m2_workspace.py tests/ui/test_m2_browser_flow.py
git commit -m "feat: add M2 interview and outline workspace"
```

### Task 9: M2 Evaluation Harness and Acceptance Report

**Files:**
- Create: `scripts/check_m2_gate.py`
- Create: `scripts/run_m2_evaluation.py`
- Create: `tests/scripts/test_check_m2_gate.py`
- Create: `tests/fixtures/m2/cases.json`
- Create: `docs/evaluations/m2-gate-report.md`
- Modify: `PPT agent.md`

**Interfaces:**
- Produces: `artifacts/m2/pytest.xml`, `artifacts/m2/evaluation.json`, and a nonzero gate exit on failure.
- Measures: key-field coverage, invalid-question rate, interview turns, gap-to-research traceability, version accuracy, approval violations, and secret leakage.

- [ ] **Step 1: Write failing gate tests**

```python
def test_gate_rejects_unapproved_transition(tmp_path):
    write_evaluation(tmp_path, approval_violations=1)
    assert check_m2_gate(tmp_path) == ["approval violations: 1"]


def test_gate_rejects_missing_research_traceability(tmp_path):
    write_evaluation(tmp_path, research_traceability=0.95)
    assert check_m2_gate(tmp_path) == ["research traceability below 100%"]
```

- [ ] **Step 2: Create four isolated evaluation cases**

`cases.json` contains one synthetic case each for:

- topic only;
- sufficient Markdown;
- insufficient material with unknown answer;
- mixed Markdown, DOCX, PDF, and PPTX.

Each case declares expected required fields, forbidden repeated questions, maximum 15 interview turns, expected slide range, and expected research gaps. Use no copyrighted public deck and no external API in the gate.

- [ ] **Step 3: Implement the deterministic runner and gate**

The runner uses a scripted fake structured model and writes:

```json
{
  "schema_version": 1,
  "cases": 4,
  "key_field_coverage": 0.9,
  "invalid_question_rate": 0.0,
  "mean_interview_turns": 8.0,
  "research_traceability": 1.0,
  "version_accuracy": 1.0,
  "approval_violations": 0,
  "secret_leaks": 0
}
```

The gate requires coverage `>=0.90`, invalid-question rate `<=0.10`, mean turns `<=15`, research traceability `==1.0`, version accuracy `==1.0`, and zero approval violations, test failures, or secret leaks.

- [ ] **Step 4: Run the complete offline suite and gate**

Run:

```powershell
conda run -n AI python -m pytest -m "not online" --junitxml=artifacts/m2/pytest.xml
conda run -n AI python scripts/run_m2_evaluation.py
conda run -n AI python scripts/check_m2_gate.py
```

Expected: all offline tests PASS and the M2 gate exits 0.

- [ ] **Step 5: Perform manual DeepSeek and UI acceptance**

With `DEEPSEEK_API_KEY` set only in the current console, run one topic-only case and one Markdown case. Confirm generated questions are relevant, no known field is repeated, outline editing works, and the approved version produces research tasks. Record only metrics and safe error categories, never prompts, raw material, responses, or the Key.

- [ ] **Step 6: Write report and update roadmap**

Record exact test counts, gate metrics, manual results, known limitations, and the entry contract for the networking milestone. Mark M2 complete in `PPT agent.md` only after automated gate and user UI acceptance pass.

- [ ] **Step 7: Final validation**

Run:

```powershell
git diff --check
conda run -n AI python -m compileall -q src scripts
conda run -n AI python scripts/check_m2_gate.py
git status --short
```

Expected: no whitespace errors, compilation succeeds, gate exits 0, and only intended report/roadmap files remain uncommitted.

- [ ] **Step 8: Commit**

```powershell
git add scripts/check_m2_gate.py scripts/run_m2_evaluation.py tests/scripts/test_check_m2_gate.py tests/fixtures/m2/cases.json docs/evaluations/m2-gate-report.md "PPT agent.md"
git commit -m "docs: complete M2 requirements and outline gate"
```
