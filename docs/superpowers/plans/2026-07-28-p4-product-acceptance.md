# P4 Product Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute this plan task-by-task in the current session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the first-version product with a clear local workflow, recoverable failures, reproducible end-to-end evidence, Office acceptance instructions, and a fail-closed final gate.

**Architecture:** Keep the existing M1–P3 modules unchanged in responsibility. Add a small read-only journey projection for the Streamlit workspace, harden only exposed failure boundaries, then validate the approved-outline → Blueprint → SlideDSL → PPTX path with deterministic fixtures and machine-readable evidence.

**Tech Stack:** Python 3.10, Pydantic 2, SQLite, Streamlit AppTest, python-pptx, pytest, existing Windows PowerPoint STA worker.

## Global Constraints

- Local Windows 11 application; no cloud deployment, WPS or macOS/Linux COM support.
- API keys remain session-only and must not enter SQLite, logs, exports, traces or error messages.
- `Project State + Deck Blueprint` remains the semantic source of truth; PPTX remains a generated artifact.
- Do not add a new framework, background queue or model call.
- Online and Office evidence remain separate from the offline gate.
- Each task follows failing test → minimal implementation → targeted tests → full regression → machine-readable evidence → commit.

---

### Task 1: Workflow progress and next-action guidance

**Files:**
- Create: `src/pptmaker/ui/journey.py`
- Modify: `src/pptmaker/ui/app.py`
- Create: `tests/ui/test_journey.py`
- Modify: `tests/ui/test_app_smoke.py`

**Interfaces:**
- Produce `build_journey(project_id, database) -> JourneyView`.
- `JourneyView` contains six stable stages: requirements, outline, research, blueprint, assets and PPTX.
- Each stage is `pending`, `current` or `complete` and supplies one short next-action message; it never exposes model output or secret values.

- [ ] Add tests for a new project, approved outline, approved Blueprint, `PPTX_READY`, `COMPLETED` and recoverable failure.
- [ ] Implement the projection using existing repositories only.
- [ ] Render a compact progress block above the project workspace and keep existing controls in place.
- [ ] Run `pytest tests/ui/test_journey.py tests/ui/test_app_smoke.py -v`.
- [ ] Commit with `feat: clarify local ppt workflow progress`.

### Task 2: Safe recovery at interactive boundaries

**Files:**
- Modify: `src/pptmaker/ui/blueprint_workspace.py`
- Modify: `src/pptmaker/ui/m3_workspace.py`
- Modify: `src/pptmaker/ui/state.py`
- Modify: `tests/ui/test_blueprint_workspace.py`
- Modify: `tests/ui/test_m3_workspace.py`
- Modify: `tests/ui/test_state.py`

**Interfaces:**
- Produce safe user categories for provider, research, asset, build and render failures.
- Preserve a valid `PPTX_READY` artifact when preview rendering fails.
- A failed Blueprint generation or asset search remains retryable without corrupting the latest approved versions.

- [ ] Add tests that inject provider, asset, build and render failures and assert no URL, authorization value, model body or traceback reaches UI text.
- [ ] Catch failures at the button action that owns them; retain existing data and display one actionable retry message.
- [ ] Add a visible retry action for `FAILED_RECOVERABLE`; do not add automatic retries.
- [ ] Run `pytest tests/ui/test_state.py tests/ui/test_blueprint_workspace.py tests/ui/test_m3_workspace.py -v`.
- [ ] Commit with `fix: make interactive generation failures recoverable`.

### Task 3: End-to-end deterministic acceptance suite

**Files:**
- Create: `tests/acceptance/test_blueprint_to_pptx.py`
- Create: `tests/acceptance/fixtures.py`
- Create: `src/pptmaker/evaluation/product_acceptance.py`
- Create: `tests/evaluation/test_product_acceptance.py`

**Interfaces:**
- Build a representative approved 10-page Blueprint containing cover, section, cards, comparison, timeline, process, chart, image-text, quote and ending pages.
- Produce `evaluate_deck(blueprint, specs, pptx_path) -> ProductAcceptanceReport`.
- Report requirement coverage, title-conclusion rate, severe geometry defects, text-density violations, public-fact traceability, asset attribution and repair delta.

- [ ] Add a full offline test that compiles, inspects, builds and reopens the fixture PPTX.
- [ ] Assert page order/count, editable chart/text, no placeholders, no severe bounds/overlap defects, source notes and unchanged semantic titles.
- [ ] Add threshold tests matching the approved specification: coverage ≥90%, title conclusions ≥90%, severe overflow 0%, density violations ≤5%, public traceability ≥95%, repair defects decrease.
- [ ] Implement metric calculations from persisted structures, not screenshots or subjective heuristics.
- [ ] Run `pytest tests/acceptance tests/evaluation -v`.
- [ ] Commit with `test: add deterministic product acceptance suite`.

### Task 4: Final gate, Office checklist and delivery documentation

**Files:**
- Create: `scripts/check_p4_product_acceptance_gate.py`
- Create: `tests/scripts/test_check_p4_product_acceptance_gate.py`
- Create: `docs/evaluations/p4-product-acceptance-report.md`
- Create: `docs/manual-acceptance.md`
- Modify: `README.md`

**Interfaces:**
- The P4 gate requires named JUnit evidence for journey guidance, safe recovery, end-to-end compilation, thresholds, prior P1–P3 gates and secret scanning.
- Offline completion cannot claim Office, DeepSeek, Bocha or image-network checks.
- Manual acceptance supplies exact commands and observable pass criteria.

- [ ] Add fail-closed tests for missing evidence, failed prior gates, leaked secret patterns and absent acceptance metrics.
- [ ] Run the full offline suite and write JUnit evidence under `artifacts/p4-product-acceptance/`.
- [ ] Run all prior gates plus the P4 gate and record exact results.
- [ ] Document environment setup, launch, workflow, recovery, API-key handling, Office render test and final human visual checklist.
- [ ] Run `git diff --check` and a repository secret scan.
- [ ] Commit with `test: close p4 product acceptance gate`.

## Final manual acceptance

The user runs the documented online provider/search checks and the PowerPoint integration suite, then generates one representative deck and scores narrative continuity, image relevance, readability, editability and first-draft usefulness. P4 is offline-complete only when all automated gates pass; final product acceptance is complete only after those manual checks pass.
