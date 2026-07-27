# P1 Two-Stage Outline and Deck Blueprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the current `DeckOutline` as a low-cost overview, then generate, version, review, and approve a detailed `DeckBlueprint` before PPT compilation.

**Architecture:** Add a focused `pptmaker.blueprint` package with versioned Pydantic contracts, staged generation, deterministic validation, and SQLite persistence. The Streamlit workspace exposes Blueprint generation only for an approved overview and prevents M3 generation until a Blueprint version is approved.

**Tech Stack:** Python 3.10.20, Pydantic 2, SQLite, existing OpenAI-compatible `StructuredModel`, Streamlit, pytest.

## Global Constraints

- `DeckOutline` remains the overview contract; do not overload it with full slide copy.
- `DeckBlueprint` is the semantic source for later PPT generation.
- Every public fact reference is a `FactRecord.id`; free-text source names are insufficient.
- Blueprint generation uses separate skeleton and page-batch calls; no full-deck monolithic prompt.
- API keys remain session-only.
- No real image download is implemented in P1; pages may carry asset search requirements but not fake asset IDs.
- Existing approved outlines and M1/M2 projects must remain readable without database migration commands.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/pptmaker/blueprint/models.py` | Deck Bible, section, page, version and validation contracts |
| `src/pptmaker/blueprint/generator.py` | Staged skeleton and page-batch generation |
| `src/pptmaker/blueprint/quality.py` | Deterministic Blueprint validation |
| `src/pptmaker/blueprint/repository.py` | SQLite version lifecycle |
| `src/pptmaker/ui/blueprint_workspace.py` | Review, edit, compare, approve and restore UI |
| `src/pptmaker/ui/m2_workspace.py` | Mount Blueprint workspace after overview |
| `src/pptmaker/ui/m3_workspace.py` | Require approved Blueprint before generation |
| `scripts/check_p1_blueprint_gate.py` | Machine-readable P1 gate |

### Task 1: Define Blueprint Contracts and Quality Rules

**Files:**
- Create: `src/pptmaker/blueprint/__init__.py`
- Create: `src/pptmaker/blueprint/models.py`
- Create: `src/pptmaker/blueprint/quality.py`
- Create: `tests/blueprint/test_models.py`
- Create: `tests/blueprint/test_quality.py`

**Interfaces:**
- Produces: `DeckBible`, `BlueprintSection`, `BlueprintPage`, `BlueprintDraft`, `DeckBlueprint`, `BlueprintReview`
- Produces: `review_blueprint(blueprint: DeckBlueprint, fact_ids: set[str]) -> BlueprintReview`

- [ ] **Step 1: Write failing model tests**

```python
import pytest
from pydantic import ValidationError

from pptmaker.blueprint.models import (
    BlueprintPage,
    DeckBible,
    VisualPlan,
)


def test_page_rejects_more_than_three_supporting_points():
    with pytest.raises(ValidationError):
        BlueprintPage(
            page_id="p1",
            order=1,
            page_type="content",
            purpose="说明价值",
            conclusion_title="效率提升来自流程自动化",
            primary_message="自动化减少重复劳动",
            supporting_points=["一", "二", "三", "四"],
            visual=VisualPlan(kind="cards", layout="three_cards"),
        )


def test_deck_bible_limits_palette_and_fonts():
    with pytest.raises(ValidationError):
        DeckBible(
            scenario="路演",
            audience="投资人",
            objective="获得投资",
            narrative_framework="SCQA",
            narrative="从痛点到投资价值",
            action="进入尽调",
            primary_color="#165DFF",
            accent_colors=["#FF8800", "#00AA88", "#FF00FF"],
            neutral_colors=["#111111", "#FFFFFF"],
            title_font="微软雅黑",
            body_font="思源黑体",
            extra_font="宋体",
        )
```

- [ ] **Step 2: Verify tests fail because the package does not exist**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/blueprint/test_models.py -q
```

Expected: import failure.

- [ ] **Step 3: Implement the contracts**

`models.py` must define:

```python
from typing import Literal

from pydantic import BaseModel, Field, model_validator


BlueprintStatus = Literal["DRAFT", "APPROVED", "SUPERSEDED"]
VisualKind = Literal[
    "none", "chart", "diagram", "photo", "illustration", "icons", "cards"
]


class DeckBible(BaseModel):
    schema_version: Literal[1] = 1
    scenario: str = Field(min_length=1, max_length=200)
    audience: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1, max_length=300)
    narrative_framework: str = Field(min_length=1, max_length=100)
    narrative: str = Field(min_length=1, max_length=1_000)
    action: str = Field(default="", max_length=300)
    terminology: dict[str, str] = Field(default_factory=dict, max_length=100)
    forbidden_content: list[str] = Field(default_factory=list, max_length=50)
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_colors: list[str] = Field(default_factory=list, max_length=2)
    neutral_colors: list[str] = Field(default_factory=list, max_length=4)
    title_font: str = Field(min_length=1, max_length=100)
    body_font: str = Field(min_length=1, max_length=100)
    extra_font: str | None = None
    image_style: str = Field(default="", max_length=300)
    icon_style: str = Field(default="", max_length=200)
    footer: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def _two_fonts_only(self):
        fonts = {self.title_font, self.body_font}
        if self.extra_font:
            fonts.add(self.extra_font)
        if len(fonts) > 2:
            raise ValueError("deck may use at most two fonts")
        return self


class VisualPlan(BaseModel):
    kind: VisualKind
    layout: str = Field(min_length=1, max_length=100)
    ratio: str = Field(default="", max_length=50)
    alignment: Literal["left", "center", "right"] = "left"
    description: str = Field(default="", max_length=500)
    chart_type: str | None = Field(default=None, max_length=50)
    highlights: list[str] = Field(default_factory=list, max_length=2)


class BlueprintPage(BaseModel):
    page_id: str = Field(min_length=1)
    order: int = Field(ge=1, le=100)
    page_type: str = Field(min_length=1, max_length=50)
    purpose: str = Field(min_length=1, max_length=500)
    conclusion_title: str = Field(min_length=1, max_length=100)
    primary_message: str = Field(min_length=1, max_length=500)
    supporting_points: list[str] = Field(default_factory=list, max_length=3)
    detail: str = Field(default="", max_length=1_000)
    speaker_notes: str = Field(default="", max_length=5_000)
    forbidden_content: list[str] = Field(default_factory=list, max_length=20)
    previous_bridge: str = Field(default="", max_length=300)
    next_bridge: str = Field(default="", max_length=300)
    visual: VisualPlan
    fact_ids: list[str] = Field(default_factory=list, max_length=50)
    asset_search_query: str = Field(default="", max_length=500)
    asset_ids: list[str] = Field(default_factory=list, max_length=20)
    estimated_seconds: int = Field(default=60, ge=10, le=600)
    density: Literal["light", "medium", "heavy"] = "medium"
    memory_anchor: str = Field(default="", max_length=200)


class BlueprintSection(BaseModel):
    section_id: str = Field(min_length=1)
    order: int = Field(ge=1, le=20)
    title: str = Field(min_length=1, max_length=200)
    audience_question: str = Field(min_length=1, max_length=500)
    conclusion: str = Field(min_length=1, max_length=500)
    relation_to_previous: str = Field(default="", max_length=300)
    page_ids: list[str] = Field(min_length=1, max_length=50)


class BlueprintDraft(BaseModel):
    bible: DeckBible
    sections: list[BlueprintSection] = Field(min_length=1, max_length=20)
    pages: list[BlueprintPage] = Field(min_length=1, max_length=100)


class DeckBlueprint(BlueprintDraft):
    schema_version: Literal[1] = 1
    project_id: str
    outline_version: int = Field(ge=1)
    version: int = Field(ge=1)
    status: BlueprintStatus
    parent_version: int | None = Field(default=None, ge=1)
    change_summary: str = Field(default="", max_length=1_000)


class BlueprintReview(BaseModel):
    passed: bool
    defects: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Add and implement deterministic quality tests**

Tests:

```python
def test_review_rejects_missing_page_and_unknown_fact():
    blueprint = sample_blueprint()
    blueprint.pages.pop()
    blueprint.pages[0].fact_ids = ["missing"]
    review = review_blueprint(blueprint, {"fact-1"})
    assert "section_page_missing" in review.defects
    assert "unknown_fact_reference" in review.defects


def test_review_rejects_four_heavy_pages_in_a_row():
    blueprint = sample_blueprint(page_count=4)
    blueprint.pages = [
        page.model_copy(update={"density": "heavy"})
        for page in blueprint.pages
    ]
    assert "density_rhythm_invalid" in review_blueprint(
        blueprint, set()
    ).defects
```

`review_blueprint` checks unique/contiguous page order, unique page IDs, exact section references, maximum three consecutive heavy pages, duplicate titles, unknown facts, total estimated duration against requirement only when supplied later, and no fake `asset_ids`.

- [ ] **Step 5: Run tests**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/blueprint/test_models.py tests/blueprint/test_quality.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add src/pptmaker/blueprint tests/blueprint
git commit -m "feat: define deck blueprint contracts"
```

### Task 2: Persist Blueprint Versions

**Files:**
- Create: `src/pptmaker/blueprint/repository.py`
- Create: `tests/blueprint/test_repository.py`

**Interfaces:**
- Produces: `BlueprintRepository`
- Methods: `create`, `get`, `list`, `approve`, `restore`

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_create_supersedes_previous_draft(tmp_path):
    repo = BlueprintRepository(tmp_path / "db.sqlite")
    first = repo.create(sample_blueprint(version=1))
    second = repo.create(sample_blueprint(version=1))
    assert repo.get("p1", first.version).status == "SUPERSEDED"
    assert second.version == 2
    assert second.status == "DRAFT"


def test_approve_supersedes_old_approved_version(tmp_path):
    repo = BlueprintRepository(tmp_path / "db.sqlite")
    first = repo.create(sample_blueprint(version=1))
    repo.approve("p1", first.version)
    second = repo.create(
        sample_blueprint(version=1).model_copy(
            update={"parent_version": first.version}
        )
    )
    approved = repo.approve("p1", second.version)
    assert approved.status == "APPROVED"
    assert repo.get("p1", first.version).status == "SUPERSEDED"


def test_restore_creates_new_draft(tmp_path):
    repo = BlueprintRepository(tmp_path / "db.sqlite")
    first = repo.create(sample_blueprint(version=1))
    restored = repo.restore("p1", first.version)
    assert restored.version == 2
    assert restored.parent_version == first.version
    assert restored.status == "DRAFT"
```

- [ ] **Step 2: Verify failure**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/blueprint/test_repository.py -q
```

Expected: import failure.

- [ ] **Step 3: Implement a single-table repository**

Create `blueprints(project_id, version, outline_version, status, payload)` with primary key `(project_id, version)`. Use `BEGIN IMMEDIATE` for create/approve, mirror the proven outline lifecycle, and validate every payload with `DeckBlueprint.model_validate_json`.

- [ ] **Step 4: Run tests and commit**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/blueprint/test_repository.py -q
git add src/pptmaker/blueprint/repository.py tests/blueprint/test_repository.py
git commit -m "feat: persist deck blueprint versions"
```

### Task 3: Generate Blueprint in Stages

**Files:**
- Create: `src/pptmaker/blueprint/generator.py`
- Create: `tests/blueprint/test_generator.py`

**Interfaces:**
- Consumes: approved `DeckOutline`, `RequirementBrief`, active `FactRecord[]`, `DesignPlan`
- Produces: `generate_blueprint(...) -> DeckBlueprint`

- [ ] **Step 1: Write failing staged-call tests**

```python
def test_generator_uses_skeleton_then_page_batches():
    model = QueueModel([
        skeleton_for(outline()),
        page_batch(["p1", "p2"]),
        page_batch(["p3"]),
    ])
    result = generate_blueprint(
        outline(), brief(), facts(), design(), model, "TEST_KEY",
        batch_size=2,
    )
    assert len(model.calls) == 3
    assert [page.page_id for page in result.pages] == ["p1", "p2", "p3"]


def test_generator_never_sends_excluded_facts():
    model = valid_queue_model()
    generate_blueprint(
        outline(), brief(), [excluded_fact()], design(),
        model, "TEST_KEY",
    )
    assert all("private statement" not in call.user for call in model.calls)


def test_generator_rejects_missing_or_extra_pages():
    model = QueueModel([
        skeleton_for(outline()),
        page_batch(["p1", "unexpected"]),
    ])
    with pytest.raises(InvalidBlueprint):
        generate_blueprint(
            outline(), brief(), facts(), design(),
            model, "TEST_KEY",
        )
```

- [ ] **Step 2: Verify failure**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/blueprint/test_generator.py -q
```

- [ ] **Step 3: Implement skeleton and batch contracts**

Internal models:

```python
class BlueprintSkeleton(BaseModel):
    bible: DeckBible
    sections: list[BlueprintSection]


class BlueprintPageBatch(BaseModel):
    pages: list[BlueprintPage]
```

`generate_blueprint`:

1. rejects non-approved outlines;
2. sends requirements, approved overview, design and active fact metadata to the skeleton call;
3. partitions overview pages into batches of three by default;
4. sends each batch plus Bible, section summaries, adjacent overview pages and relevant facts;
5. verifies output page IDs exactly equal requested IDs;
6. assembles version `1`, status `DRAFT`;
7. calls `review_blueprint`;
8. raises `InvalidBlueprint(defects)` instead of persisting an invalid result.

All evidence lists are bounded before JSON serialization using the P0 limits.

- [ ] **Step 4: Run tests and commit**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/blueprint/test_generator.py -q
git add src/pptmaker/blueprint/generator.py tests/blueprint/test_generator.py
git commit -m "feat: generate deck blueprint in stages"
```

### Task 4: Add Blueprint Review and Approval UI

**Files:**
- Create: `src/pptmaker/ui/blueprint_workspace.py`
- Modify: `src/pptmaker/ui/m2_workspace.py`
- Modify: `src/pptmaker/ui/m3_workspace.py`
- Create: `tests/ui/test_blueprint_workspace.py`
- Modify: `tests/ui/test_m2_workspace.py`

**Interfaces:**
- Produces: `render_blueprint_workspace(project, projects, approved_outline)`
- M3 consumes: latest approved `DeckBlueprint`

- [ ] **Step 1: Add failing AppTest coverage**

```python
def test_approved_outline_shows_blueprint_action(monkeypatch, tmp_path):
    project = seeded_project_with_approved_outline(monkeypatch, tmp_path)
    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)
    assert any(
        button.label == "生成详细施工大纲"
        for button in app.button
    )


def test_m3_generation_is_hidden_until_blueprint_approved(
    monkeypatch, tmp_path
):
    seeded_project_with_approved_outline(monkeypatch, tmp_path)
    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)
    assert not any(button.label == "生成 PPT" for button in app.button)


def test_blueprint_version_switches_after_save(monkeypatch, tmp_path):
    project = seeded_project_with_draft_blueprint(monkeypatch, tmp_path)
    app = AppTest.from_file("src/pptmaker/ui/app.py").run(timeout=10)
    next(button for button in app.button if button.label == "保存为新版本").click()
    app.run(timeout=10)
    assert "v2" in selected_blueprint_label(app)
```

- [ ] **Step 2: Verify tests fail**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/ui/test_blueprint_workspace.py tests/ui/test_m2_workspace.py -q
```

- [ ] **Step 3: Implement the workspace**

The workspace:

- appears only after an outline is approved;
- shows latest research status and blocks generation when web policy is `ALWAYS` without completed research;
- generates a draft with `generate_blueprint`;
- displays Bible, sections and expandable pages;
- edits conclusion title, primary message, supporting points, notes, visual kind/layout, bridges, fact IDs and asset search query;
- saves edits as a new draft and queues selection before rerun;
- approves only a passing `review_blueprint`;
- displays version, status, parent comparison counts and restore action.

M3 changes:

```python
approved_blueprints = [
    item for item in BlueprintRepository(projects.path).list(project.id)
    if item.status == "APPROVED"
]
if not approved_blueprints:
    return
```

Do not yet replace `plan_content` with Blueprint compilation; P3 performs that migration. In P1 the approved Blueprint is a required semantic gate while existing M3 content generation remains temporarily compatible.

- [ ] **Step 4: Run UI tests and commit**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/ui/test_blueprint_workspace.py tests/ui/test_m2_workspace.py tests/ui/test_app_smoke.py -q
git add src/pptmaker/ui/blueprint_workspace.py src/pptmaker/ui/m2_workspace.py src/pptmaker/ui/m3_workspace.py tests/ui/test_blueprint_workspace.py tests/ui/test_m2_workspace.py
git commit -m "feat: add deck blueprint approval workspace"
```

### Task 5: Add P1 Blueprint Gate and Regression

**Files:**
- Create: `scripts/check_p1_blueprint_gate.py`
- Create: `tests/scripts/test_check_p1_blueprint_gate.py`
- Create: `docs/evaluations/p1-blueprint-gate-report.md`

**Interfaces:**
- Produces: machine-readable pass/fail for contracts, persistence, staged generation, UI approval, and M3 gate

- [ ] **Step 1: Write failing gate tests**

```python
def test_gate_requires_all_suites(tmp_path):
    write_junit(tmp_path, passed=True)
    write_metrics(
        tmp_path,
        schema_valid=True,
        staged_generation=True,
        version_lifecycle=True,
        m3_requires_approval=True,
    )
    assert check_gate(tmp_path) == []


def test_gate_rejects_monolithic_generation(tmp_path):
    write_valid_evidence(tmp_path, staged_generation=False)
    assert "staged generation failed" in check_gate(tmp_path)
```

- [ ] **Step 2: Implement gate and run complete tests**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/blueprint tests/ui tests/scripts/test_check_p1_blueprint_gate.py -q
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest -m "not online and not office" -q
C:\Users\DELL\.conda\envs\AI\python.exe scripts/check_m1_gate.py
C:\Users\DELL\.conda\envs\AI\python.exe scripts/check_m2_gate.py
C:\Users\DELL\.conda\envs\AI\python.exe scripts/check_m3_gate.py
C:\Users\DELL\.conda\envs\AI\python.exe scripts/check_p1_blueprint_gate.py
```

Expected: all offline tests and M1/M2/M3/P1 gates pass.

- [ ] **Step 3: Write the measured report and commit**

Record actual test counts and limitations. Do not claim P2 research timing or real images are complete.

```powershell
git add scripts/check_p1_blueprint_gate.py tests/scripts/test_check_p1_blueprint_gate.py docs/evaluations/p1-blueprint-gate-report.md
git commit -m "test: close p1 deck blueprint gate"
```
