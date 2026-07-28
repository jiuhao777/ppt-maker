# Pre-outline Research and Rework Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute this plan inline, task by task.

**Goal:** Ensure freshness-sensitive outlines use verified web facts before generation and make deterministic rework defects recoverable.

**Architecture:** Reuse `FreshnessService`, `ResearchRun`, Fact Store and existing Streamlit workspace. Add one explicit stale-content approval transition, feed active facts into outline generation, and normalize only safe structural defects before reflection.

**Tech Stack:** Python 3.10, Pydantic 2, SQLite, LangGraph, Streamlit AppTest, pytest.

## Global Constraints

- API keys remain session-only.
- Search content reaches prompts only through normalized Fact Store records.
- User choice overrides automatic routing.
- Local rework cannot modify unaffected pages.
- No new dependency or background service.

### Task 1: Pre-outline research gate

**Files:**
- Modify: `src/pptmaker/research/service.py`
- Modify: `src/pptmaker/ui/m2_workspace.py`
- Modify: `tests/m2/test_freshness_integration.py`
- Modify: `tests/ui/test_m2_workspace.py`

- [ ] Test that required research with a Key completes before outline generation and active facts enter the outline prompt.
- [ ] Test that `AUTO` without a Key requires explicit stale-content approval.
- [ ] Test that approval permits generation and a new analysis clears the approval.
- [ ] Replace the “after outline” UI copy and preserve post-outline page research.
- [ ] Run targeted M2 and UI tests.

### Task 2: Deterministic rework normalization

**Files:**
- Modify: `src/pptmaker/m2/rework.py`
- Modify: `tests/m2/test_rework.py`
- Modify: `tests/m2/test_outline_services.py`

- [ ] Test page-count synchronization, page reordering, key-point truncation and numeric-gap creation.
- [ ] Test byte-equivalent preservation of unaffected local pages.
- [ ] Normalize before reflection, then retain one model retry only for unresolved defects.
- [ ] Run targeted tests and the full offline suite.

### Task 3: Closure

**Files:**
- Modify: `docs/evaluations/p4-product-acceptance-report.md`

- [ ] Run M2/P4 gates and `git diff --check`.
- [ ] Record regression results and commit the fix.
