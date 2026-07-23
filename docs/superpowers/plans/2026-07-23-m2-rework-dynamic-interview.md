# M2 Rework, Version Navigation, and Dynamic Interview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add controlled global/local AI outline rework, reliable version navigation, concise task-aware interviews, and deduplicated research tasks without expanding beyond M2.

**Architecture:** Pydantic contracts define task-specific interview fields and two-stage rework. Deterministic services constrain question count, unaffected-page preservation, and research-task deduplication; SQLite commits successful rework atomically. Streamlit stores only transient impact previews and switches versions on the rerun before widget creation.

**Tech Stack:** Python 3.10.20, Pydantic 2.13.4, SQLite, LangGraph 1.2.9, OpenAI-compatible structured output, Streamlit 1.59.1, pytest 9.0.2.

## Global Constraints

- Keep the six core fields, but ask only material gaps that can change the outline.
- Add at most two controlled task-specific fields; total blocking questions must never exceed eight.
- Every question expresses one idea, includes a reason, offers two to four short choices where useful, and retains “不知道/不确定”.
- AI rework is two-stage: impact analysis, then explicit user confirmation, then final generation.
- Global rework may change the whole outline; local rework may change only confirmed impacted page IDs.
- A failed, cancelled, or invalid rework creates no outline version and changes no research tasks.
- New manual, restored, or AI-generated versions automatically become the selected UI version after rerun.
- Old versions remain readable and retain parent version, creation method, and change summary.
- Research tasks are not fixed in count and are deduplicated before persistence.
- API Keys remain runtime method arguments and Streamlit session values only.
- Do not implement web search, detailed copy, PPTX generation, or any M3 feature.

---

### Task 1: Rework and Version Metadata Contracts

**Files:**
- Modify: `src/pptmaker/m2/models.py`
- Modify: `src/pptmaker/m2/repository.py`
- Modify: `src/pptmaker/m2/__init__.py`
- Modify: `tests/m2/test_models.py`
- Modify: `tests/m2/test_m2_repository.py`

**Interfaces:**
- Produces: `TaskType`, `CreationMethod`, `ReworkMode`, `ReworkRequest`, `ReworkImpact`.
- Extends: `RequirementBrief.task_type`, `RequirementBrief.special_requirements`.
- Extends: `InterviewQuestion.options`.
- Extends: `DeckOutline.creation_method`, `DeckOutline.change_summary`.
- Produces: `M2Repository.commit_rework(current, draft, impact, brief) -> DeckOutline`.

- [ ] **Step 1: Write failing contract and atomicity tests**

```python
def test_interview_question_has_bounded_choices():
    question = InterviewQuestion(
        field="funding_goal",
        text="本轮计划融资多少？",
        reason="融资目标会改变资金用途页面。",
        options=["500 万", "1000 万"],
    )
    assert len(question.options) == 2


def test_rework_commit_sets_metadata_and_updates_brief_atomically(repository):
    current = repository.create_outline(outline())
    impact = ReworkImpact(
        mode="global",
        feedback="制造业改为服务业",
        impacted_page_ids=[current.pages[0].id],
        reasons={current.pages[0].id: "行业变化"},
        requirement_updates={"purpose": "服务业 AI 转型"},
        refresh_research_tasks=True,
    )
    draft = DeckOutlineDraft(
        narrative="服务业 AI 转型",
        target_slides=1,
        pages=[page(title="服务业机会")],
    )
    brief = RequirementBrief(project_id=current.project_id)

    created = repository.commit_rework(current, draft, impact, brief)

    assert created.version == 2
    assert created.creation_method == "AI_GLOBAL_REWORK"
    assert created.parent_version == 1
    assert repository.get_brief(current.project_id).purpose.value == "服务业 AI 转型"
```

- [ ] **Step 2: Run focused tests**

Run:

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m2/test_models.py tests/m2/test_m2_repository.py -v
```

Expected: FAIL because rework metadata and `commit_rework` do not exist.

- [ ] **Step 3: Add bounded models**

```python
TaskType = Literal[
    "work_report", "project_report", "pitch", "thesis",
    "teaching", "data_report", "event", "custom",
]
CreationMethod = Literal[
    "GENERATED", "MANUAL_EDIT", "AI_GLOBAL_REWORK",
    "AI_LOCAL_REWORK", "RESTORED",
]
ReworkMode = Literal["global", "local"]


class ReworkRequest(BaseModel):
    mode: ReworkMode
    feedback: str = Field(min_length=1, max_length=2_000)
    selected_page_ids: list[str] = Field(default_factory=list, max_length=100)


class ReworkImpact(BaseModel):
    mode: ReworkMode
    feedback: str
    impacted_page_ids: list[str] = Field(min_length=1, max_length=100)
    reasons: dict[str, str]
    requirement_updates: dict[str, str] = Field(default_factory=dict)
    refresh_research_tasks: bool
```

Add `options: list[str] = Field(default_factory=list, max_length=4)` to `InterviewQuestion`. Add `task_type: TaskType = "custom"` and `special_requirements: dict[str, RequirementField]` to `RequirementBrief`. Add default `creation_method="GENERATED"` and bounded `change_summary=""` to `DeckOutline`.

Update existing repository transitions: `update_outline` writes `MANUAL_EDIT`, and `restore_outline` writes `RESTORED`. Existing generated outlines retain `GENERATED`.

- [ ] **Step 4: Implement one transactional rework commit**

Validate every impacted ID exists in `current`. Build a new `DeckOutline` from the validated draft, assign the next version, parent, creation method, and summary, then in one `BEGIN IMMEDIATE` transaction:

1. update the old draft to `SUPERSEDED`;
2. update `m2_briefs`;
3. insert the new draft.

Rollback on any exception. Do not call `create_outline`, which opens a second connection.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m2/test_models.py tests/m2/test_m2_repository.py tests/projects -q
```

Expected: PASS.

```powershell
git add src/pptmaker/m2 tests/m2/test_models.py tests/m2/test_m2_repository.py
git commit -m "feat: add M2 rework contracts"
```

### Task 2: Concise Task-Aware Interview Planning

**Files:**
- Modify: `src/pptmaker/m2/interview.py`
- Modify: `tests/m2/test_interview.py`
- Modify: `tests/fixtures/m2/cases.json`

**Interfaces:**
- Produces: `SPECIAL_FIELDS: dict[TaskType, tuple[str, ...]]`.
- Produces: `remaining_question_count(brief) -> int`.
- Preserves: `rank_gaps`, `plan_next_question`, `accept_unknown`, `extract_requirements`.

- [ ] **Step 1: Write failing variation and limit tests**

```python
def test_pitch_and_thesis_receive_different_special_questions():
    pitch = complete_brief(task_type="pitch", special_requirements={})
    thesis = complete_brief(task_type="thesis", special_requirements={})

    assert plan_next_question(pitch).field == "special:funding_goal"
    assert plan_next_question(thesis).field == "special:research_method"


def test_question_count_never_exceeds_eight():
    brief = RequirementBrief(project_id="p1", task_type="pitch")
    fields = []
    while question := plan_next_question(brief):
        fields.append(question.field)
        brief = accept_unknown(brief, question.field, "待验证")
    assert 1 <= len(fields) <= 8
    assert len(fields) == len(set(fields))


def test_question_is_simple_and_has_choices():
    question = plan_next_question(
        complete_brief(audience=RequirementField())
    )
    assert len(question.text) <= 40
    assert 2 <= len(question.options) <= 4
```

- [ ] **Step 2: Run interview tests**

Run:

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m2/test_interview.py -v
```

Expected: FAIL on missing task-specific fields and options.

- [ ] **Step 3: Add controlled templates**

```python
SPECIAL_FIELDS = {
    "work_report": ("outcome_metric", "decision_request"),
    "project_report": ("outcome_metric", "main_risk"),
    "pitch": ("funding_goal", "competitive_advantage"),
    "thesis": ("research_method", "main_conclusion"),
    "teaching": ("learner_level", "learning_goal"),
    "data_report": ("time_range", "comparison_baseline"),
    "event": ("call_to_action", "participant_profile"),
    "custom": (),
}
```

Define one short question, reason, and two-to-four options for each controlled field. Core gaps keep their existing priority. Special gaps have lower priority than missing purpose/scenario/audience and higher priority than style. Slice ranked gaps to eight.

`accept_unknown` handles `special:<name>` by updating `special_requirements[name]`; it must not permit arbitrary field names outside the selected task template.

- [ ] **Step 4: Make extraction classify task type**

Keep `RequirementBrief` as the structured schema. Update the system prompt to choose one closed `task_type` and populate only its controlled `special_requirements`. Merge rules remain user-first and confidence-aware.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m2/test_interview.py tests/providers/test_structured.py -q
```

Expected: PASS.

```powershell
git add src/pptmaker/m2/interview.py tests/m2/test_interview.py tests/fixtures/m2/cases.json
git commit -m "feat: ask concise task-aware questions"
```

### Task 3: Two-Stage Global and Local AI Rework

**Files:**
- Create: `src/pptmaker/m2/rework.py`
- Modify: `src/pptmaker/m2/__init__.py`
- Create: `tests/m2/test_rework.py`

**Interfaces:**
- Produces: `analyze_rework(current, request, model, api_key) -> ReworkImpact`.
- Produces: `apply_rework(current, brief, chunks, impact, model, api_key) -> DeckOutlineDraft`.
- Produces: `validate_rework_scope(current, draft, impact) -> None`.

- [ ] **Step 1: Write failing global, local, and failure tests**

```python
def test_global_industry_rework_removes_old_industry_everywhere():
    current = manufacturing_outline()
    impact = global_impact(current, "改为服务业")
    model = FakeModel([service_outline_draft()])

    draft = apply_rework(current, brief(), [], impact, model, "TEST_KEY")

    assert "制造业" not in draft.model_dump_json()
    assert "服务业" in draft.model_dump_json()


def test_local_rework_preserves_unaffected_pages_exactly():
    current = three_page_outline()
    impact = local_impact(current, impacted=[current.pages[1].id])
    model = FakeModel([draft_with_only_middle_changed(current)])

    draft = apply_rework(current, brief(), [], impact, model, "TEST_KEY")

    assert draft.pages[0] == current.pages[0]
    assert draft.pages[2] == current.pages[2]


def test_invalid_local_rework_is_rejected_before_repository_write():
    with pytest.raises(InvalidRework):
        validate_rework_scope(current, draft_changing_unapproved_page(), impact)
```

- [ ] **Step 2: Run rework tests**

Run:

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m2/test_rework.py -v
```

Expected: FAIL because `pptmaker.m2.rework` does not exist.

- [ ] **Step 3: Implement impact analysis**

Call `StructuredModel.generate(ReworkImpact, ...)` with current page IDs, titles, objectives, gaps, request mode, selected page IDs, and feedback. Validate:

- global impact IDs are a subset of current IDs;
- local impact includes every selected ID;
- local impact IDs are a subset of current IDs;
- reasons exist for every impacted ID.

Raise `InvalidRework("返工影响范围无效")` with no raw model response.

- [ ] **Step 4: Implement final generation and scope validation**

Global mode prompt includes the complete current outline, brief, material locations, impact, and feedback. Local mode prompt additionally instructs the model to return the complete outline while copying unaffected pages exactly.

After structured output:

```python
for old_page in current.pages:
    if old_page.id not in impact.impacted_page_ids:
        if new_by_id.get(old_page.id) != old_page:
            raise InvalidRework("局部返工修改了影响范围外页面")
```

Run existing `reflect_outline`; reject remaining deterministic defects. The repository is not called inside this service.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m2/test_rework.py tests/m2/test_outline_services.py -q
```

Expected: PASS.

```powershell
git add src/pptmaker/m2/rework.py src/pptmaker/m2/__init__.py tests/m2/test_rework.py
git commit -m "feat: add controlled M2 outline rework"
```

### Task 4: Research Task Deduplication

**Files:**
- Modify: `src/pptmaker/m2/models.py`
- Modify: `src/pptmaker/m2/outlines.py`
- Modify: `src/pptmaker/m2/repository.py`
- Modify: `tests/m2/test_outline_services.py`
- Modify: `tests/m2/test_m2_repository.py`

**Interfaces:**
- Extends: `ResearchTask.related_page_ids`.
- Produces: `deduplicate_research_tasks(tasks) -> list[ResearchTask]`.
- Changes: `build_research_tasks` returns deduplicated tasks.

- [ ] **Step 1: Write failing deduplication tests**

```python
def test_equivalent_research_gaps_merge_across_pages():
    tasks = [
        research("市场规模？", "data", "p1"),
        research("市场规模", "data", "p2"),
    ]

    merged = deduplicate_research_tasks(tasks)

    assert len(merged) == 1
    assert merged[0].related_page_ids == ["p1", "p2"]


def test_same_words_with_different_material_types_do_not_merge():
    tasks = [
        research("市场规模", "data", "p1"),
        research("市场规模", "image", "p1"),
    ]
    assert len(deduplicate_research_tasks(tasks)) == 2
```

- [ ] **Step 2: Run outline tests**

Run:

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m2/test_outline_services.py -v
```

Expected: FAIL because deduplication does not exist.

- [ ] **Step 3: Implement deterministic normalization**

Normalize Unicode with NFKC, lowercase Latin text, remove whitespace and terminal punctuation, and key by `(normalized_question, material_type)`. Preserve first-seen order and highest priority; combine unique page IDs in page order.

Do not use embeddings or another LLM call in M2.

- [ ] **Step 4: Replace tasks per approved version**

`build_research_tasks` calls the deduplicator. Existing `replace_research_tasks` remains the only persistence path, so approving a new version atomically replaces only that version’s task set.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m2/test_outline_services.py tests/m2/test_m2_repository.py -q
```

Expected: PASS.

```powershell
git add src/pptmaker/m2/models.py src/pptmaker/m2/outlines.py src/pptmaker/m2/repository.py tests/m2
git commit -m "feat: deduplicate M2 research tasks"
```

### Task 5: Streamlit Rework and Version Navigation

**Files:**
- Modify: `src/pptmaker/ui/m2_workspace.py`
- Modify: `src/pptmaker/ui/state.py`
- Modify: `tests/ui/test_m2_workspace.py`

**Interfaces:**
- Produces session keys `m2_pending_version_<project_id>` and `m2_rework_impact_<project_id>`.
- Consumes Tasks 1–4 services.

**Required skill:** Use `developing-with-streamlit` before implementation.

- [ ] **Step 1: Write failing auto-switch and rework-panel tests**

```python
def test_saved_version_becomes_selected_on_next_rerun(app_with_outline):
    click_save_new_version(app_with_outline)
    app_with_outline.run()
    assert selected_outline_version(app_with_outline) == "v2"


def test_all_versions_remain_selectable(app_with_two_versions):
    labels = outline_version_options(app_with_two_versions)
    assert labels == [
        "v1 · SUPERSEDED · GENERATED",
        "v2 · DRAFT · MANUAL_EDIT",
    ]


def test_rework_requires_impact_confirmation(app_with_outline):
    assert button(app_with_outline, "分析影响范围")
    assert not button(app_with_outline, "确认并生成新版本")
```

- [ ] **Step 2: Run UI tests**

Run:

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/ui/test_m2_workspace.py -v
```

Expected: FAIL because version switching and rework controls do not exist.

- [ ] **Step 3: Fix selection before widget creation**

Before calling `st.selectbox`, pop the pending version and assign the widget key:

```python
widget_key = f"m2_outline_version_{project.id}"
pending_key = f"m2_pending_version_{project.id}"
if pending_key in st.session_state:
    st.session_state[widget_key] = st.session_state.pop(pending_key)
```

Every successful manual save, restore, or AI rework sets `pending_key` to the new version, then calls `st.rerun()`. Format options with status and creation method.

- [ ] **Step 4: Add the two-stage rework UI**

Render mode radio, page multiselect for local mode, and feedback text area. “分析影响范围” calls `analyze_rework` and stores only `ReworkImpact.model_dump()` in session state. Show impacted pages and reasons. Only then render “确认并生成新版本”.

Confirmation calls `apply_rework`, then `repository.commit_rework`; on success clear impact state, set pending version, and rerun. On any safe error display a fixed message and keep the original version selected.

- [ ] **Step 5: Render concise interview choices**

Display `question.options` as a radio group plus “自行输入”. Show `remaining_question_count(brief)` as an estimate. Preserve the existing free-text and unknown paths.

- [ ] **Step 6: Run UI and regression tests**

Run:

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/ui tests/m2 -q
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest -m "not online and not office" -q
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/pptmaker/ui/m2_workspace.py src/pptmaker/ui/state.py tests/ui/test_m2_workspace.py
git commit -m "fix: improve M2 rework and version UX"
```

### Task 6: Gate, Report, and Real Acceptance

**Files:**
- Modify: `tests/fixtures/m2/cases.json`
- Modify: `scripts/run_m2_evaluation.py`
- Modify: `scripts/check_m2_gate.py`
- Modify: `tests/scripts/test_check_m2_gate.py`
- Modify: `docs/evaluations/m2-gate-report.md`
- Modify: `PPT agent.md`

**Interfaces:**
- Adds metrics: `max_interview_turns`, `task_type_variation`, `rework_scope_accuracy`, `research_deduplication`, `version_auto_selection`.

- [ ] **Step 1: Add failing gate metric tests**

```python
def test_gate_rejects_excessive_interview(tmp_path):
    write_evidence(tmp_path, max_interview_turns=9)
    assert check_m2_gate(tmp_path) == ["interview exceeds 8 questions"]


def test_gate_rejects_rework_scope_leak(tmp_path):
    write_evidence(tmp_path, rework_scope_accuracy=0.99)
    assert check_m2_gate(tmp_path) == ["rework scope accuracy below 100%"]
```

- [ ] **Step 2: Extend deterministic cases**

Include pitch, thesis, global manufacturing-to-service rework, local single-page rework, duplicate research gaps, and version-selection evidence. The runner must execute real deterministic services, not hard-code passing metrics.

- [ ] **Step 3: Run complete automated gate**

Run:

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest -m "not online and not office" --junitxml=artifacts/m2/pytest.xml -q
C:\Users\DELL\.conda\envs\AI\python.exe scripts/run_m2_evaluation.py
C:\Users\DELL\.conda\envs\AI\python.exe scripts/check_m2_gate.py
```

Expected: all tests pass and gate exits 0.

- [ ] **Step 4: Repeat real user acceptance**

Use DeepSeek in the local UI:

1. generate a manufacturing outline;
2. globally rework it to services and verify no manufacturing residue;
3. locally rework one page and verify unrelated pages remain identical;
4. save another manual version and verify automatic selection;
5. inspect v1, v2, and the current version;
6. approve and verify deduplicated research tasks;
7. create a pitch and a thesis project and confirm their necessary questions differ and remain simple.

- [ ] **Step 5: Update report and milestone state**

Record exact automated metrics and the user’s result. Mark M2 formally accepted only after real UI confirmation.

- [ ] **Step 6: Commit**

```powershell
git add tests/fixtures/m2/cases.json scripts/run_m2_evaluation.py tests/scripts/test_check_m2_gate.py docs/evaluations/m2-gate-report.md "PPT agent.md"
git commit -m "docs: close M2 rework acceptance"
```
