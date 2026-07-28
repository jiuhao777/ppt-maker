# Blueprint Asset Slots and Layout Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade detailed outlines to schema-versioned page construction plans with executable geometry and up to four independently selected images per slide.

**Architecture:** Blueprint schema 2 owns semantic content, normalized layout elements, and image slots. A deterministic layout planner converts page intent into valid normalized regions; asset storage and selection are scoped by slot; M3 consumes those regions directly instead of guessing image placement from page type. Schema 1 payloads are migrated in memory and saved as new schema 2 versions.

**Tech Stack:** Python 3.10, Pydantic v2, SQLite, Streamlit, python-pptx/SlideDSL, pytest.

## Global Constraints

- Support Windows 11 PowerPoint.
- A page contains zero to four image slots.
- Layout coordinates use normalized values from 0 to 1.
- Ordinary users edit natural-language intent and key options; exact coordinates stay in advanced settings.
- Existing schema 1 blueprints remain readable.
- API keys and other secrets are never persisted or logged.
- Keep existing SSRF, MIME, size, pixel-count, redirect, and decode validation for downloaded images.
- Every task starts with a failing test and ends with focused regression tests.
- Do not refactor unrelated modules.

---

## File Structure

- `src/pptmaker/blueprint/models.py`: schema 2 models and validation.
- `src/pptmaker/blueprint/migration.py`: schema 1 payload conversion only.
- `src/pptmaker/blueprint/layout_planner.py`: deterministic normalized geometry and readable construction summaries.
- `src/pptmaker/blueprint/generator.py`: model contract and generated draft normalization.
- `src/pptmaker/blueprint/quality.py`: blueprint approval checks.
- `src/pptmaker/blueprint/repository.py`: version loading, migration, slot selection, and approval.
- `src/pptmaker/assets/models.py`: slot-scoped asset records.
- `src/pptmaker/assets/repository.py`: one approved asset per slot.
- `src/pptmaker/assets/curator.py`: search and download per slot.
- `src/pptmaker/ui/blueprint_workspace.py`: slot cards, construction plan editor, advanced geometry.
- `src/pptmaker/m3/blueprint_compiler.py`: compile schema 2 elements and validate slot ownership.
- `src/pptmaker/m3/layouts.py`: render explicit regions, including special page types.
- Matching files under `tests/` verify each boundary.

---

### Task 1: Blueprint Schema 2 and Migration

**Files:**
- Modify: `src/pptmaker/blueprint/models.py`
- Create: `src/pptmaker/blueprint/migration.py`
- Modify: `src/pptmaker/blueprint/repository.py`
- Modify: `src/pptmaker/blueprint/__init__.py`
- Modify: `tests/blueprint/factories.py`
- Modify: `tests/blueprint/test_models.py`
- Create: `tests/blueprint/test_migration.py`
- Modify: `tests/blueprint/test_repository.py`

**Interfaces:**
- Produces: `LayoutRegion`, `LayoutElementPlan`, `AssetSlot`, schema 2 `BlueprintPage`.
- Produces: `load_blueprint(payload: str) -> DeckBlueprint`.
- Consumes later: all asset, UI, and M3 tasks use `page.asset_slots` and `page.layout_elements`.

- [ ] **Step 1: Write failing schema tests**

```python
def test_page_allows_four_unique_asset_slots():
    page = blueprint_page(
        asset_slots=[asset_slot(f"image-{n}") for n in range(4)]
    )
    assert len(page.asset_slots) == 4


def test_page_rejects_five_asset_slots():
    with pytest.raises(ValidationError):
        blueprint_page(
            asset_slots=[asset_slot(f"image-{n}") for n in range(5)]
        )


def test_region_rejects_canvas_overflow():
    with pytest.raises(ValidationError):
        LayoutRegion(x=0.8, y=0.1, width=0.3, height=0.2)
```

- [ ] **Step 2: Run schema tests and verify failure**

Run: `conda run -n AI pytest tests/blueprint/test_models.py -q`

Expected: FAIL because the schema 2 types do not exist.

- [ ] **Step 3: Add the minimal schema 2 types**

```python
class LayoutRegion(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside_canvas(self):
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("layout region must stay inside canvas")
        return self


class LayoutElementPlan(BaseModel):
    element_id: str = Field(min_length=1, max_length=100)
    kind: Literal[
        "title", "subtitle", "body", "chart", "image",
        "source", "footer", "page_number",
    ]
    region: LayoutRegion
    z_index: int = Field(default=0, ge=0, le=100)
    alignment: Literal["left", "center", "right"] = "left"
    font_size: int | None = Field(default=None, ge=10, le=72)
    color_token: str = Field(default="text_primary", max_length=50)
    content_ref: str = Field(min_length=1, max_length=100)
    fit: Literal["cover", "contain"] | None = None


class AssetSlot(BaseModel):
    slot_id: str = Field(min_length=1, max_length=100)
    role: Literal[
        "background", "hero", "logo", "photo", "screenshot",
        "illustration", "icon", "case", "decorative",
    ]
    subject: str = Field(min_length=1, max_length=300)
    search_query: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=500)
    required: bool = False
    region: LayoutRegion
    fit: Literal["cover", "contain"] = "cover"
    z_index: int = Field(default=0, ge=0, le=100)
    fallback: Literal[
        "no_image", "icon", "text", "simplified_layout"
    ] = "simplified_layout"
    selected_asset_id: str | None = Field(default=None, max_length=200)
```

Add `layout_elements: list[LayoutElementPlan]` and
`asset_slots: list[AssetSlot] = Field(default_factory=list, max_length=4)`
to `BlueprintPage`. Validate unique element IDs, unique slot IDs, and image
elements referencing real slots. Change `DeckBlueprint.schema_version` to
`Literal[2] = 2`.

- [ ] **Step 4: Write failing schema 1 migration tests**

```python
def test_schema_one_single_asset_becomes_hero_slot():
    payload = legacy_blueprint_payload(
        asset_search_query="DeepSeek logo",
        asset_ids=["asset-1"],
    )
    migrated = load_blueprint(json.dumps(payload))
    slot = migrated.pages[0].asset_slots[0]
    assert migrated.schema_version == 2
    assert slot.role == "hero"
    assert slot.search_query == "DeepSeek logo"
    assert slot.selected_asset_id == "asset-1"
```

- [ ] **Step 5: Implement deterministic migration and repository loading**

```python
def load_blueprint(payload: str) -> DeckBlueprint:
    data = json.loads(payload)
    if data.get("schema_version", 1) == 1:
        data = migrate_v1(data)
    return DeckBlueprint.model_validate(data)
```

`migrate_v1()` must create one hero slot only when the old page has a search
query or selected asset, create default layout elements through a small
legacy mapping, remove `asset_search_query` and `asset_ids`, and set
`schema_version=2`. Replace every direct
`DeckBlueprint.model_validate_json(payload)` repository read with
`load_blueprint(payload)`.

- [ ] **Step 6: Run focused tests**

Run:
`conda run -n AI pytest tests/blueprint/test_models.py tests/blueprint/test_migration.py tests/blueprint/test_repository.py -q`

Expected: all selected tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/pptmaker/blueprint tests/blueprint
git commit -m "feat: add blueprint schema two"
```

---

### Task 2: Deterministic Page Layout Planning

**Files:**
- Create: `src/pptmaker/blueprint/layout_planner.py`
- Modify: `src/pptmaker/blueprint/generator.py`
- Modify: `src/pptmaker/blueprint/quality.py`
- Create: `tests/blueprint/test_layout_planner.py`
- Modify: `tests/blueprint/test_generator.py`
- Modify: `tests/blueprint/test_quality.py`

**Interfaces:**
- Consumes: semantic `BlueprintPage` fields and proposed `AssetSlot` objects.
- Produces: `plan_page_layout(page: BlueprintPage) -> BlueprintPage`.
- Produces: `construction_summary(page: BlueprintPage) -> str`.

- [ ] **Step 1: Write failing layout tests**

```python
@pytest.mark.parametrize("count", [0, 1, 2, 3, 4])
def test_layout_planner_represents_every_image_slot(count):
    page = blueprint_page(
        asset_slots=[asset_slot(f"image-{n}") for n in range(count)]
    )
    planned = plan_page_layout(page)
    refs = {
        item.content_ref
        for item in planned.layout_elements
        if item.kind == "image"
    }
    assert refs == {item.slot_id for item in planned.asset_slots}


@pytest.mark.parametrize("page_type", ["cover", "section", "quote", "ending"])
def test_special_pages_support_a_selected_image(page_type):
    planned = plan_page_layout(
        blueprint_page(page_type=page_type, asset_slots=[asset_slot("hero")])
    )
    assert any(item.kind == "image" for item in planned.layout_elements)
```

- [ ] **Step 2: Run planner tests and verify failure**

Run: `conda run -n AI pytest tests/blueprint/test_layout_planner.py -q`

Expected: FAIL because `plan_page_layout` does not exist.

- [ ] **Step 3: Implement the smallest deterministic planner**

Implement named templates for:

- no image: full-width content;
- one image: 40/60 text-image, with background variant for cover/section/quote/ending;
- two images: text band plus two equal image cells;
- three images: one hero plus two stacked supporting images;
- four images: 2×2 image matrix plus title band.

Each template emits title, body, image, source/footer, and page-number elements
inside a 4% horizontal and vertical safe margin. Existing chart pages emit one
chart element and no decorative image unless an explicit slot exists.

- [ ] **Step 4: Normalize generated model output**

After `generate_blueprint` validates the model response, call
`plan_page_layout(page)` for each page. The model supplies subjects, roles,
search queries, purposes, and layout intent; it does not supply trusted
coordinates.

- [ ] **Step 5: Add approval quality checks**

Add defect codes for:

- `too_many_asset_slots`;
- `duplicate_asset_slot_id`;
- `duplicate_layout_element_id`;
- `invalid_layout_reference`;
- `unrepresented_asset_slot`;
- `required_asset_missing`;
- `layout_region_overlap`;
- `layout_region_out_of_bounds`.

Only overlap above the existing severe-overlap threshold blocks approval;
background images may overlap every element.

- [ ] **Step 6: Test readable construction summaries**

```python
def test_construction_summary_contains_position_and_bridge():
    summary = construction_summary(plan_page_layout(blueprint_page()))
    assert "核心结论" in summary
    assert "布局" in summary
    assert "演讲备注" in summary
    assert "逻辑衔接" in summary
```

- [ ] **Step 7: Run focused tests**

Run:
`conda run -n AI pytest tests/blueprint/test_layout_planner.py tests/blueprint/test_generator.py tests/blueprint/test_quality.py -q`

Expected: all selected tests PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/pptmaker/blueprint tests/blueprint
git commit -m "feat: plan executable slide layouts"
```

---

### Task 3: Slot-Scoped Image Search and Selection

**Files:**
- Modify: `src/pptmaker/assets/models.py`
- Modify: `src/pptmaker/assets/repository.py`
- Modify: `src/pptmaker/assets/curator.py`
- Modify: `src/pptmaker/blueprint/repository.py`
- Modify: `tests/assets/test_models.py`
- Modify: `tests/assets/test_repository.py`
- Modify: `tests/assets/test_curator.py`
- Modify: `tests/blueprint/test_repository.py`

**Interfaces:**
- Adds: `AssetRecord.slot_id: str`.
- Changes: `AssetRepository.approve(project_id, asset_id)` rejects only other assets in the same slot.
- Changes: `BlueprintRepository.select_asset(project_id, version, page_id, slot_id, asset_id)`.
- Adds: `BlueprintRepository.set_slot_fallback(project_id, version, page_id, slot_id)`.

- [ ] **Step 1: Write failing per-slot approval tests**

```python
def test_approving_second_slot_keeps_first_slot_approved(repository):
    repository.replace_candidates(PROJECT, 1, "p1", "hero", [hero])
    repository.replace_candidates(PROJECT, 1, "p1", "logo", [logo])
    repository.approve(PROJECT, hero.id)
    repository.approve(PROJECT, logo.id)
    approved = [
        item for item in repository.list_for_blueprint(PROJECT, 1)
        if item.status == "APPROVED"
    ]
    assert {(item.slot_id, item.id) for item in approved} == {
        ("hero", hero.id), ("logo", logo.id)
    }
```

- [ ] **Step 2: Run repository tests and verify failure**

Run:
`conda run -n AI pytest tests/assets/test_repository.py tests/blueprint/test_repository.py -q`

Expected: FAIL because records and methods are not slot-scoped.

- [ ] **Step 3: Add slot ownership without a destructive SQL migration**

Add `slot_id` to `AssetRecord` payload. Keep the existing SQLite columns and
query candidate payloads for slot matching, avoiding a risky table rebuild.
Change `replace_candidates` to accept `slot_id` and preserve approved records
only for that slot. Change `approve` to mark only records sharing project,
blueprint version, page, and slot as rejected.

- [ ] **Step 4: Update Blueprint selection**

```python
def select_asset(
    self,
    project_id: str,
    version: int,
    page_id: str,
    slot_id: str,
    asset_id: str,
) -> DeckBlueprint:
    # Validate asset page and slot ownership, then update only this slot.
```

`set_slot_fallback` clears only the chosen slot and sets `required=False`;
it must not change other slots or convert the whole page to `visual.kind=none`.

- [ ] **Step 5: Curate each slot independently**

Iterate through `page.asset_slots`, call the existing provider chain with
`slot.search_query`, store `slot_id` in every `AssetRecord`, and use a
slot-specific download directory:
`assets/<project>/<version>/<page>/<slot>/`.
Return diagnostics keyed by `"<page_id>:<slot_id>"`.

- [ ] **Step 6: Run focused tests**

Run:
`conda run -n AI pytest tests/assets tests/blueprint/test_repository.py -q`

Expected: all selected tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/pptmaker/assets src/pptmaker/blueprint/repository.py tests/assets tests/blueprint/test_repository.py
git commit -m "feat: select images by blueprint slot"
```

---

### Task 4: Detailed Blueprint Editor and Image Slot Cards

**Files:**
- Modify: `src/pptmaker/ui/blueprint_workspace.py`
- Modify: `src/pptmaker/ui/journey.py`
- Modify: `tests/ui/test_blueprint_workspace.py`
- Modify: `tests/ui/test_journey.py`

**Interfaces:**
- Consumes: schema 2 construction summaries, slot-scoped asset APIs, version queue helpers.
- Produces: saved edits as new Blueprint versions and automatically selects the new version.

- [ ] **Step 1: Write failing UI-state tests**

```python
def test_selecting_one_slot_does_not_clear_another(tmp_path):
    # Create two approved slot assets through the workspace helpers.
    selected = BlueprintRepository(path).get(project.id, version)
    assert {
        slot.slot_id: slot.selected_asset_id
        for slot in selected.pages[0].asset_slots
    } == {"hero": "asset-1", "logo": "asset-2"}


def test_saved_blueprint_version_is_queued_for_selection():
    state = {}
    queue_blueprint_version(state, "project", 3)
    apply_pending_blueprint_version(state, "project")
    assert state["blueprint_version_project"] == 3
```

- [ ] **Step 2: Run UI tests and verify failure**

Run:
`conda run -n AI pytest tests/ui/test_blueprint_workspace.py tests/ui/test_journey.py -q`

Expected: slot workflow tests FAIL.

- [ ] **Step 3: Render the readable construction plan**

For each page show, in order:

- purpose and conclusion;
- content hierarchy;
- deterministic construction summary;
- one card per asset slot;
- chart and highlights;
- notes and page bridges;
- advanced layout expander.

Keep normal controls semantic. In the advanced expander, use numeric inputs
for `x`, `y`, `width`, and `height` with range 0.0–1.0 and step 0.01.

- [ ] **Step 4: Render independent slot asset cards**

Each card displays role, subject, purpose, search query, position summary,
selected preview, and buttons for search, choose, replace, clear, and fallback.
Button keys include project, version, page, slot, and asset IDs. Search only
the chosen slot instead of re-running all page searches.

- [ ] **Step 5: Save edits as a new selected version**

Validate the edited page through Pydantic before `repository.create`.
On success call `queue_blueprint_version` with the returned version and
`st.rerun()`. Do not mutate a widget-owned session-state key after widget
creation.

- [ ] **Step 6: Add version comparison details**

For a selected historical version, compare against the latest version and
show page count, title, page type, element count, slot count, and selected
asset changes. Restoring still copies into a new draft.

- [ ] **Step 7: Run focused UI tests**

Run:
`conda run -n AI pytest tests/ui/test_blueprint_workspace.py tests/ui/test_journey.py tests/ui/test_app_smoke.py -q`

Expected: all selected tests PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/pptmaker/ui tests/ui
git commit -m "feat: edit detailed blueprint construction plans"
```

---

### Task 5: Compile Explicit Geometry and Multiple Images

**Files:**
- Modify: `src/pptmaker/m3/blueprint_compiler.py`
- Modify: `src/pptmaker/m3/layouts.py`
- Modify: `src/pptmaker/m3/image_fit.py`
- Modify: `tests/m3/test_blueprint_compiler.py`
- Modify: `tests/m3/test_layouts.py`
- Modify: `tests/m3/test_builder.py`

**Interfaces:**
- Consumes: `page.layout_elements`, `page.asset_slots`, and slot-owned `AssetRecord`.
- Produces: `SlideSpec` containing every selected image exactly once at its declared region.

- [ ] **Step 1: Write failing multi-image compiler tests**

```python
@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_compiler_emits_every_selected_slot(count, tmp_path):
    blueprint, assets = approved_blueprint_with_images(tmp_path, count)
    spec = compile_blueprint(blueprint, [], assets, design())[0]
    images = [element for element in spec.elements if element.type == "image"]
    assert len(images) == count


@pytest.mark.parametrize("page_type", ["cover", "section", "quote", "ending"])
def test_special_page_with_image_compiles(page_type, tmp_path):
    blueprint, assets = approved_blueprint_with_images(
        tmp_path, 1, page_type=page_type
    )
    assert compile_blueprint(blueprint, [], assets, design())
```

- [ ] **Step 2: Run M3 tests and verify failure**

Run:
`conda run -n AI pytest tests/m3/test_blueprint_compiler.py tests/m3/test_layouts.py -q`

Expected: multi-image and special-page tests FAIL.

- [ ] **Step 3: Validate exact slot ownership**

Build the approved asset map by `(page_id, slot_id)`. Reject:

- selected IDs not approved;
- page or slot mismatch;
- missing local files for required slots;
- one selected asset referenced by multiple slots;
- selected slots without image elements;
- image elements referencing unknown slots.

Optional slots with missing assets are omitted and the page is re-planned with
the remaining slots before rendering.

- [ ] **Step 4: Render normalized layout elements**

Convert normalized regions using:

```python
left = region.x * 13.333
top = region.y * 7.5
width = region.width * 13.333
height = region.height * 7.5
```

Map title/body/source/footer/page-number fields to text elements, chart
references to existing structured chart rendering, and image slot references
to existing crop/contain image logic. Sort by `z_index` before producing
`SlideSpec`.

- [ ] **Step 5: Remove page-type image guessing**

Keep existing layout helpers for schema-independent text/chart primitives,
but stop deciding whether selected images are represented from
`page.visual.kind`. All page types, including cover, section, quote, and
ending, use explicit image elements.

- [ ] **Step 6: Run geometry, builder, and compiler tests**

Run:
`conda run -n AI pytest tests/m3/test_blueprint_compiler.py tests/m3/test_layouts.py tests/m3/test_builder.py tests/m3/test_quality.py -q`

Expected: all selected tests PASS and severe overlap/overflow findings equal 0.

- [ ] **Step 7: Commit**

```powershell
git add src/pptmaker/m3 tests/m3
git commit -m "feat: compile multi-image blueprint layouts"
```

---

### Task 6: Regression, Migration, and Real PowerPoint Acceptance

**Files:**
- Modify: `tests/acceptance/fixtures.py`
- Modify: `tests/acceptance/test_product_journey.py`
- Create: `tests/acceptance/test_blueprint_asset_slots.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: the complete schema 2 UI-to-PPTX path.
- Produces: automated evidence that old projects and 0–4 image pages remain usable.

- [ ] **Step 1: Add acceptance fixtures**

Create fixtures for:

- multi-brand logo page;
- life-scene plus screenshot page;
- three-image comparison page;
- four-image matrix page;
- image-backed ending page;
- schema 1 project payload.

Use generated local test images only. Do not rely on live image providers.

- [ ] **Step 2: Add end-to-end assertions**

```python
def test_schema_one_project_generates_schema_two_pptx(tmp_path):
    project = import_legacy_project(tmp_path)
    blueprint = approve_migrated_blueprint(project)
    output = generate_pptx(project, blueprint)
    assert output.is_file()
    assert inspect_pptx(output).slide_count == len(blueprint.pages)


def test_optional_image_removal_reflows_without_placeholder(tmp_path):
    output = generate_after_optional_slot_fallback(tmp_path)
    report = inspect_rendered_deck(output)
    assert report.placeholders == 0
    assert report.severe_overlaps == 0
```

- [ ] **Step 3: Run the complete offline suite**

Run:
`conda run -n AI pytest -q --deselect=tests/powerpoint/test_worker_integration.py`

Expected: all offline tests PASS; online and Office-only tests may be explicitly
skipped or deselected, never silently counted as pass.

- [ ] **Step 4: Run M0/P2/P3/P4 gates**

Run the existing repository gate commands in their documented order.

Expected: every required gate reports PASS and writes machine-readable
evidence.

- [ ] **Step 5: Run approved Office integration tests**

Run:
`conda run -n AI pytest tests/powerpoint/test_worker_integration.py -q`

Expected: all Office tests PASS, no orphaned `POWERPNT.EXE`, and exported slide
images are in numeric order.

- [ ] **Step 6: Generate and inspect a real multi-image PPTX**

Generate the five acceptance page types, open/render through the PowerPoint
worker, and verify:

- file opens successfully;
- every selected image appears once in the intended area;
- no severe overlap or overflow;
- no image placeholder remains;
- optional-image fallback still produces a valid slide.

- [ ] **Step 7: Update user-facing documentation**

Document that detailed outlines contain executable layout plans, pages support
up to four image slots, advanced geometry is optional, old projects migrate
when a new version is saved, and PowerPoint edits do not sync back.

- [ ] **Step 8: Final commit**

```powershell
git add tests/acceptance README.md docs
git commit -m "test: accept blueprint asset slot workflow"
```

---

## Final Verification

Run:

```powershell
git status --short
conda run -n AI pytest -q --deselect=tests/powerpoint/test_worker_integration.py
conda run -n AI pytest tests/powerpoint/test_worker_integration.py -q
```

Expected:

- working tree contains only intentional changes or is clean;
- complete offline suite passes;
- Office integration passes;
- all project gates pass;
- a real schema 2 multi-image PPTX opens and renders without severe defects.
