# P2 Research and Asset Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute this plan task-by-task in the current session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move factual research behind outline approval and provide traceable, safely downloaded image candidates for Blueprint approval.

**Architecture:** Keep Bocha as the fact-search provider. Add a small asset package with provider adapters, SQLite persistence, secure image validation, and curation tied to a Blueprint version and page. Openverse is the primary anonymous image source and Wikimedia Commons is the fallback. The approved Blueprint remains the semantic source of truth; an asset is usable by P3 only after explicit approval.

**Tech Stack:** Python 3.10, Pydantic 2, SQLite, httpx, Pillow, Streamlit, pytest.

## Global Constraints

- API keys remain only in `st.session_state`; never write them to SQLite, files, logs, traces, or exports.
- Online facts enter prompts only after normalization into Fact Store records.
- Remote images are never loaded directly by the browser; the server fetches and verifies them first.
- Every remote URL and redirect is checked by the existing SSRF-safe fetcher.
- Strict mode accepts only public-domain, CC0, CC BY, and CC BY-SA assets. Loose mode may retain restricted or unknown assets only with a visible risk warning, author, and source link.
- No candidate is compiled into PPT until its status is `APPROVED`.
- A missing or rejected image degrades to a chart, diagram, cards, or a complete no-image layout; no placeholder box is exported.
- Each task follows failing test → minimal implementation → targeted tests → regression tests → commit.

---

### Task 1: Asset contracts and SQLite store

**Files:**
- Create: `src/pptmaker/assets/__init__.py`
- Create: `src/pptmaker/assets/models.py`
- Create: `src/pptmaker/assets/repository.py`
- Create: `tests/assets/test_models.py`
- Create: `tests/assets/test_repository.py`

**Interfaces:**
- Produce `AssetCandidate`, `AssetRecord`, `AssetStatus`, `LicenseMode`, and `AssetRepository`.
- `AssetRepository.replace_candidates(project_id, blueprint_version, page_id, records)` atomically replaces only that page's unapproved candidates.
- `AssetRepository.approve(project_id, asset_id)` approves one asset and rejects other candidates for the same Blueprint page.
- `AssetRepository.list_for_blueprint(project_id, blueprint_version, page_id=None)` restores candidates after refresh.

- [ ] Write tests that reject cross-project records, invalid dimensions, missing attribution in loose mode, and unusable license/status combinations.
- [ ] Run `pytest tests/assets/test_models.py tests/assets/test_repository.py -v` and confirm collection or assertion failure.
- [ ] Implement only the versioned models and repository operations required by the tests.
- [ ] Re-run the targeted tests and confirm PASS.
- [ ] Run `pytest tests/research tests/blueprint -q`.
- [ ] Commit with `feat: persist versioned asset candidates`.

### Task 2: Openverse and Wikimedia provider adapters

**Files:**
- Create: `src/pptmaker/assets/providers.py`
- Create: `tests/assets/test_providers.py`

**Interfaces:**
- Produce protocol `AssetProvider.search(query: str, count: int) -> list[AssetCandidate]`.
- Produce `OpenverseProvider` using `GET https://api.openverse.org/v1/images/`.
- Produce `WikimediaProvider` using MediaWiki `action=query&generator=search&prop=imageinfo`.
- Produce `FallbackAssetSearch.search(query, count)` that deduplicates by landing/original URL and uses Wikimedia only when Openverse returns too few usable results.
- Provider exceptions expose only `timeout`, `rate_limit`, `invalid_response`, or `unavailable`.

- [ ] Add `httpx.MockTransport` tests for field mapping, license normalization, mature-result rejection, deduplication, timeout, rate limit, and fallback.
- [ ] Confirm the targeted tests fail before implementation.
- [ ] Implement adapters with injected transport, finite timeout, `follow_redirects=False`, and at most one bounded retry for HTTP 429/5xx.
- [ ] Confirm `pytest tests/assets/test_providers.py -v` passes without internet.
- [ ] Commit with `feat: add traceable image search providers`.

### Task 3: Secure image download and verification

**Files:**
- Create: `src/pptmaker/assets/downloader.py`
- Modify: `src/pptmaker/security/fetcher.py`
- Create: `tests/assets/test_downloader.py`
- Modify: `tests/security/test_fetcher.py`

**Interfaces:**
- Extend `safe_fetch` with an optional returned final content type while preserving its existing bytes API.
- Produce `VerifiedImage` and `download_image(candidate, destination_dir, resolver, ...)`.
- Validate MIME against PNG/JPEG/WebP, Pillow-decoded format, maximum 10 MiB, dimensions from 320×180 through 12,000×12,000, decompression-bomb errors, and SHA-256.
- Write to a task-local temporary file and atomically publish only after verification.

- [ ] Add tests for private redirect targets, MIME/decoded-format mismatch, truncated images, excessive pixels, excessive bytes, hash stability, and no partial file after failure.
- [ ] Confirm the new tests fail.
- [ ] Implement the smallest compatible fetcher extension and downloader.
- [ ] Run `pytest tests/assets/test_downloader.py tests/security/test_fetcher.py -v`.
- [ ] Run `pytest tests/security tests/m0/test_security_probe.py -q`.
- [ ] Commit with `feat: securely download and verify images`.

### Task 4: Post-outline research service

**Files:**
- Create: `src/pptmaker/research/post_outline.py`
- Modify: `src/pptmaker/research/service.py`
- Modify: `src/pptmaker/ui/m2_workspace.py`
- Create: `tests/research/test_post_outline.py`
- Modify: `tests/m2/test_freshness_integration.py`

**Interfaces:**
- Produce `PostOutlineResearch.run(project_id, approved_outline, policy, decision, bocha_key) -> ResearchRun`.
- Queries come from the approved outline's research tasks, are deduplicated and secret-filtered, and never exceed five searches.
- Initial requirement analysis stores the freshness decision but performs no network call.
- `ALWAYS` without a verified key remains blocked; `AUTO` without a key records `SKIPPED_NO_KEY`; `NEVER` records `NOT_REQUIRED`.

- [ ] Add tests proving analysis makes zero search calls, approval creates research tasks, and explicit research executes those tasks only after approval.
- [ ] Confirm the tests fail.
- [ ] Move the call site from `_render_materials` to the approved-outline research action and preserve safe failure states.
- [ ] Run `pytest tests/research tests/m2 -q`.
- [ ] Commit with `feat: run factual research after outline approval`.

### Task 5: Blueprint asset curation

**Files:**
- Create: `src/pptmaker/assets/curator.py`
- Modify: `src/pptmaker/blueprint/models.py`
- Modify: `src/pptmaker/blueprint/generator.py`
- Create: `tests/assets/test_curator.py`
- Modify: `tests/blueprint/test_generator.py`

**Interfaces:**
- Produce `AssetCurator.curate(project_id, blueprint, license_mode)`.
- Search only pages whose `visual_plan.kind` is `photo` or `illustration` and whose query is non-empty.
- Download at most three verified thumbnails per eligible page.
- Persist per-page failures without failing Blueprint generation.
- Blueprint approval requires every referenced `asset_id` to be approved and bound to the same project/version/page.

- [ ] Add tests for adaptive no-search pages, per-page candidate caps, strict/loose filtering, fallback after invalid images, and binding enforcement.
- [ ] Confirm failure before implementation.
- [ ] Implement curation and the approval validation hook.
- [ ] Run `pytest tests/assets tests/blueprint -q`.
- [ ] Commit with `feat: curate assets for blueprint approval`.

### Task 6: Streamlit research and candidate approval UI

**Files:**
- Modify: `src/pptmaker/ui/m2_workspace.py`
- Modify: `src/pptmaker/ui/blueprint_workspace.py`
- Create: `tests/ui/test_research_asset_flow.py`

**Interfaces:**
- After outline approval, show research state, explicit run/retry action, facts, and exclusion controls.
- After Blueprint draft generation, show locally verified thumbnails, author, license, source, risk badge, select, reject, search again, and no-image actions.
- Strict/loose mode is a project-level non-secret preference.
- M3 remains hidden until Blueprint and all selected assets are approved.

- [ ] Add AppTest coverage for the approval sequence, no-key behavior, loose-mode warning, refresh persistence, and no remote image URL rendered into browser markup.
- [ ] Confirm the AppTest fails.
- [ ] Implement the minimal UI and stable widget keys.
- [ ] Run `pytest tests/ui/test_research_asset_flow.py -v`.
- [ ] Run `pytest tests/ui -q`.
- [ ] Commit with `feat: add research and asset approval workspace`.

### Task 7: P2 gate and regression evidence

**Files:**
- Create: `scripts/check_p2_research_assets_gate.py`
- Create: `tests/scripts/test_check_p2_research_assets_gate.py`
- Create: `docs/evaluations/p2-research-assets-gate-report.md`
- Modify: `README.md`

**Interfaces:**
- Gate requires named evidence for post-outline timing, provider mapping, SSRF redirects, image verification, license modes, approval binding, persistence, and UI flow.
- Online smoke checks are reported separately and cannot turn missing offline evidence into PASS.

- [ ] Add a failing gate test with one required case omitted.
- [ ] Implement the gate parser and confirm fail-closed behavior.
- [ ] Run all offline tests with JUnit output.
- [ ] Run M1, M2, M3, P1, and P2 gates.
- [ ] Record exact test counts, skipped online checks, residual risks, and manual acceptance steps.
- [ ] Commit with `test: close p2 research and asset gate`.

## Manual acceptance after Task 7

1. Start Streamlit, create a project, choose `AUTO`, and submit a current-information topic.
2. Confirm no search occurs before the overview outline is approved.
3. Approve the outline and run research; verify current facts display source links and can be excluded.
4. Generate the detailed Blueprint; verify only appropriate pages receive image candidates.
5. Switch between strict and loose modes; loose candidates must show author, original link, license, and risk.
6. Approve one image, refresh the page, and confirm the selection persists.
7. Reject all images for one page and confirm the page becomes a complete no-image visual plan rather than a placeholder.
8. Approve the Blueprint and confirm PPT generation becomes available.
