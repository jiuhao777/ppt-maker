# P3 Blueprint-to-PPTX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute this plan task-by-task in the current session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compile the approved Deck Blueprint and approved assets directly into an editable, traceable, visually varied PPTX without the legacy Content Planner.

**Architecture:** Add a deterministic Blueprint-to-SlideDSL compiler, then render SlideDSL through focused layout and PPTX builder layers. Semantic decisions remain in the approved Blueprint; the compiler may normalize aliases and fit content but must not invent facts or rewrite conclusions. Generation artifacts and status are persisted by Blueprint version so refresh never loses a completed file.

**Tech Stack:** Python 3.10, Pydantic 2, python-pptx, SQLite, Pillow, existing PowerPoint STA worker, Streamlit AppTest, pytest.

## Global Constraints

- `Project State + Deck Blueprint` is the semantic source of truth; PPTX is a generated artifact.
- Only an `APPROVED` Blueprint matching the approved outline can generate PPTX.
- Only `APPROVED` assets bound to the same project, Blueprint version and page may enter PPTX.
- No LLM call occurs between Blueprint approval and SlideDSL compilation.
- Text, shapes, tables and charts remain editable. Photographs and illustrations remain raster images.
- Public facts and images retain source, author and license attribution in slide footers or notes.
- No image placeholder is exported.
- Default canvas is 16:9. Ordinary titles are at least 32 pt, body text at least 18 pt, and safe margins are at least 0.5 inch.
- Output is written to a task-local temporary file, reopened and validated, then atomically published.
- API keys remain session-only and never enter artifacts, logs, SQLite or PPTX metadata.
- Each task follows failing test → minimal implementation → targeted tests → full offline regression → commit.

---

### Task 1: Blueprint and SlideDSL production contracts

**Files:**
- Modify: `src/pptmaker/blueprint/models.py`
- Modify: `src/pptmaker/m3/models.py`
- Create: `src/pptmaker/m3/blueprint_compiler.py`
- Create: `tests/m3/test_blueprint_compiler.py`
- Modify: `tests/blueprint/test_models.py`

**Interfaces:**
- Add optional `ChartData(categories, series)` to `VisualPlan`.
- Add `animation_level: Literal["none", "simple"]` to `DeckBible`, default `simple`.
- Add SlideDSL elements `ImageElement`, `ChartElement`, and `LineElement`.
- Add `speaker_notes`, `source_references`, and `transition` to `SlideSpec`.
- Produce `compile_blueprint(blueprint, facts, assets, design) -> list[SlideSpec]`.

- [ ] Write failing tests proving compilation rejects non-approved Blueprints, mismatched facts/assets and unresolved photo pages.
- [ ] Add tests proving page order, conclusion titles, notes, facts, approved local image paths and simple transitions survive compilation.
- [ ] Implement the minimal contracts and compiler; do not call a model or the old `plan_content`.
- [ ] Run `pytest tests/m3/test_blueprint_compiler.py tests/blueprint/test_models.py -v`.
- [ ] Run `pytest tests/blueprint tests/assets -q`.
- [ ] Commit with `feat: compile approved blueprint to slide dsl`.

### Task 2: Formal layout library

**Files:**
- Create: `src/pptmaker/m3/layouts.py`
- Modify: `src/pptmaker/m3/blueprint_compiler.py`
- Create: `tests/m3/test_layouts.py`
- Modify: `tests/m3/test_m3_evaluation.py`

**Interfaces:**
- Produce `layout_page(page, bible, design, fact_map, asset_map) -> SlideSpec`.
- Support every formal page type: `cover`, `contents`, `section`, `conclusion`, `text`, `image_text`, `cards`, `comparison`, `timeline`, `process`, `architecture`, `data_chart`, `case`, `quote`, `interaction`, `qa`, `ending`.
- Normalize layout aliases but fail safely on unknown page types.
- Use at least six visibly distinct geometry families while preserving one Deck Bible.

- [ ] Add one representative case for every formal page type.
- [ ] Add geometry assertions for canvas bounds, safe margins and severe overlaps.
- [ ] Add density assertions: maximum three supporting points, no body font below 18 pt, no exported placeholder.
- [ ] Implement only the layout primitives required by the cases.
- [ ] Run `pytest tests/m3/test_layouts.py tests/m3/test_m3_evaluation.py -v`.
- [ ] Commit with `feat: add production slide layout library`.

### Task 3: Editable PPTX builder

**Files:**
- Modify: `src/pptmaker/m3/builder.py`
- Create: `src/pptmaker/m3/image_fit.py`
- Modify: `tests/m3/test_builder.py`
- Create: `tests/m3/test_image_fit.py`

**Interfaces:**
- Render text, bullets, shapes, lines, tables, native charts and verified images.
- Crop images to fill without stretching.
- Add source footers and speaker notes.
- Add a simple fade transition only when `SlideSpec.transition == "fade"`.
- Produce `build_pptx(specs, design, output_path) -> Path` using atomic publication.

- [ ] Add tests reopening PPTX and verifying slide count, 16:9 dimensions, editable text/table/chart, image aspect fit, notes, source footers and transition XML.
- [ ] Add failure tests proving missing image paths and invalid chart data leave no published PPTX.
- [ ] Implement cover-crop calculations independently, then integrate the new element renderers.
- [ ] Reopen the temporary PPTX with python-pptx before `os.replace`.
- [ ] Run `pytest tests/m3/test_builder.py tests/m3/test_image_fit.py -v`.
- [ ] Commit with `feat: build editable sourced pptx from slide dsl`.

### Task 4: Deterministic generation quality checks

**Files:**
- Create: `src/pptmaker/m3/quality.py`
- Create: `tests/m3/test_quality.py`
- Modify: `src/pptmaker/m3/blueprint_compiler.py`

**Interfaces:**
- Produce `inspect_specs(specs) -> SpecQualityReport`.
- Check page count/order, bounds, severe overlap, minimum font size, missing source, missing asset, duplicate titles and placeholder elements.
- Produce `repair_specs(specs, report) -> list[SlideSpec]` for bounded deterministic fixes only: clamp safe margins, remove empty elements, shorten duplicate footers and switch an image page without an approved image to a complete no-image layout.
- Reject output if repair does not reduce defects.

- [ ] Add failing defect-detection tests and scope-preservation hashes for unaffected pages.
- [ ] Add a single-repair test proving defects decrease and unaffected page payloads remain identical.
- [ ] Implement inspection and one bounded repair pass.
- [ ] Run `pytest tests/m3/test_quality.py tests/m3/test_blueprint_compiler.py -v`.
- [ ] Commit with `feat: validate and bound slide dsl repairs`.

### Task 5: Versioned generation artifacts

**Files:**
- Modify: `src/pptmaker/m3/repository.py`
- Create: `src/pptmaker/m3/artifacts.py`
- Modify: `tests/m3/test_m3_repository.py`
- Create: `tests/m3/test_artifacts.py`

**Interfaces:**
- Add `GenerationArtifact` with project ID, Blueprint version, status, PPTX path/hash, render paths, quality report and timestamps.
- States: `RUNNING`, `PPTX_READY`, `RENDERED`, `FAILED_RECOVERABLE`, `COMPLETED`.
- Persist SlideDSL and artifact records by `(project_id, blueprint_version)`.
- Verify every restored path remains inside the configured data directory and hash matches before download.

- [ ] Add round-trip, refresh recovery, path escape, stale hash, interrupted generation and secret-absence tests.
- [ ] Implement repository migration and atomic artifact publishing.
- [ ] Run `pytest tests/m3/test_m3_repository.py tests/m3/test_artifacts.py -v`.
- [ ] Commit with `feat: persist versioned ppt generation artifacts`.

### Task 6: Replace the legacy Streamlit generation path

**Files:**
- Modify: `src/pptmaker/ui/m3_workspace.py`
- Modify: `src/pptmaker/ui/blueprint_workspace.py`
- Create: `tests/ui/test_m3_workspace.py`
- Modify: `tests/ui/test_blueprint_workspace.py`

**Interfaces:**
- Generate from the latest matching approved Blueprint using `compile_blueprint`; do not call `plan_content`.
- Restore completed PPTX and thumbnails from SQLite after refresh.
- Show safe stages: compile, inspect, build, render, complete.
- Rendering failure preserves a downloadable PPTX and records `PPTX_READY`.
- Regeneration creates a new artifact for the current Blueprint version and never overwrites another version.

- [ ] Add AppTest coverage proving the old planner is not called, approved assets are compiled, refresh restores download, render failure degrades safely, and non-approved Blueprint hides generation.
- [ ] Implement stable widget keys without writing API keys or file bytes to `st.session_state`.
- [ ] Run `pytest tests/ui/test_m3_workspace.py tests/ui/test_blueprint_workspace.py -v`.
- [ ] Run `pytest tests/ui -q`.
- [ ] Commit with `feat: generate ppt directly from approved blueprint`.

### Task 7: P3 gate and Office evidence

**Files:**
- Create: `scripts/check_p3_blueprint_pptx_gate.py`
- Create: `tests/scripts/test_check_p3_blueprint_pptx_gate.py`
- Create: `docs/evaluations/p3-blueprint-pptx-gate-report.md`
- Modify: `README.md`

**Interfaces:**
- Gate requires named JUnit evidence for every page type, Blueprint-only compilation, real images, native charts, notes, sources, no placeholders, atomic output, refresh recovery and safe render degradation.
- Offline gate and Office gate remain separate.

- [ ] Add fail-closed gate tests for missing page-type, image, chart and persistence evidence.
- [ ] Generate full offline JUnit evidence and run M1, M2, M3, P1, P2 and P3 gates.
- [ ] Run python-pptx reopen validation on every generated fixture deck.
- [ ] Record exact counts and unresolved online/Office checks.
- [ ] Provide one interactive terminal command for the final Office render test, deferred until the user's final manual acceptance.
- [ ] Commit with `test: close p3 blueprint pptx gate`.

## Final manual acceptance deferred by user

After all implementation phases are complete, the user will:

1. Generate decks containing a photograph, native chart, table, timeline, architecture page, quote and ending.
2. Open each PPTX in Windows 11 PowerPoint and edit text, tables and chart data.
3. Verify images are cropped without distortion and every external asset has attribution.
4. Verify speaker notes and simple fade transitions.
5. Confirm no placeholder, severe overlap, clipping or missing page.
6. Refresh Streamlit and download the same persisted artifact again.
