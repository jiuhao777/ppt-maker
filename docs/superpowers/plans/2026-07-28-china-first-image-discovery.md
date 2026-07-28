# China-first Image Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute this plan inline, task by task.

**Goal:** Reliably obtain usable images on ordinary Chinese networks without license or author filtering while retaining download security.

**Architecture:** Keep the existing `AssetProvider → AssetCurator → AssetRepository` contract. Add composable query expansion, domestic search providers and Bocha page-image discovery; replace two-provider fallback with a resilient provider chain; expose structured curation counts and remove attribution from user-facing output.

**Tech Stack:** Python 3.10, httpx, Pydantic 2, BeautifulSoup-free standard HTML parsing, Pillow, Streamlit AppTest, pytest.

## Global Constraints

- No API key is persisted.
- Webpage text never enters an Agent prompt.
- SSRF, redirect, MIME, size, pixel and decode checks remain mandatory.
- A provider failure cannot stop later providers.
- No image placeholder is exported.

### Task 1: Personal image contracts and diagnostics

**Files:**
- Modify: `src/pptmaker/assets/models.py`
- Modify: `src/pptmaker/assets/curator.py`
- Modify: `src/pptmaker/assets/repository.py`
- Modify: `tests/assets/test_curator.py`
- Modify: `tests/assets/test_repository.py`

- [ ] Accept candidates without author or license metadata.
- [ ] Remove license filtering while keeping source URLs.
- [ ] Persist per-page search, download, validation and usable counts.
- [ ] Keep five verified candidates and test safe failure categories.

### Task 2: China-first provider chain

**Files:**
- Modify: `src/pptmaker/assets/providers.py`
- Create: `src/pptmaker/assets/web_images.py`
- Modify: `tests/assets/test_providers.py`
- Create: `tests/assets/test_web_images.py`

- [ ] Add deterministic Chinese query variants.
- [ ] Add isolated Sogou, 360 and Baidu response adapters.
- [ ] Add Bocha result-page main-image extraction using safe HTML fetches.
- [ ] Implement deduplicating provider chain with per-provider timeout/failure continuation.
- [ ] Test malformed responses, duplicates and fallback ordering.

### Task 3: UI and generation integration

**Files:**
- Modify: `src/pptmaker/ui/blueprint_workspace.py`
- Modify: `src/pptmaker/m3/layouts.py`
- Modify: `tests/ui/test_blueprint_workspace.py`
- Modify: `tests/m3/test_blueprint_compiler.py`

- [ ] Pass the session-only Bocha Key into image discovery.
- [ ] Display diagnostic counts and concise failure categories.
- [ ] Stop displaying image author/license/source in UI and PPTX.
- [ ] Automatically convert unresolved image pages to a complete no-image layout during approval/generation.

### Task 4: Regression and closure

**Files:**
- Modify: `docs/evaluations/p4-product-acceptance-report.md`

- [ ] Run asset, security, Blueprint, M3 and UI tests.
- [ ] Run full offline regression and P2/P3/P4 gates.
- [ ] Run secret scan and `git diff --check`.
- [ ] Record results and commit.
