# M3 Slide DSL and PPT Builder Implementation Plan

> **For agentic workers:** Implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver end-to-end generation from approved DeckOutline to downloadable `.pptx` with thumbnail previews.

**Architecture:** Design Planner runs first (user preset or AI) to determine visual style; Content Planner then generates copy informed by that style. Both are single-call AI planners with one retry each. A deterministic Spec Compiler converts them to SlideSpec elements with safe coordinates and overflow handling; a deterministic PPT Builder writes python-pptx with font fallback. PowerPoint rendering reuses M0's validated worker. Thumbnails and pptx bytes are cached in session_state.

**Tech Stack:** Python 3.10.20, Pydantic 2.13.4, python-pptx 1.0.2, Pillow 12.3.0, StructuredModel (M1), PowerPoint Worker (M0), Streamlit 1.59.1, pytest 9.0.2.

## Global Constraints

- AI planners each get one repair retry on schema validation failure; second failure becomes `FAILED_RECOVERABLE`.
- Spec Compiler and PPT Builder must never call an LLM (exception: Compiler overflow step 2 may use a single model call for text truncation).
- PPT Builder must use `choose_font()` with fallback chain for every font assignment.
- AI-generated content must cite verified_facts when available; conflicting model memory yields to facts.
- Color contrast ratio (primary vs background) must be ≥ 4.5:1 (WCAG AA).
- All elements must stay within 16:9 canvas with ≥ 0.5" vertical and ≥ 0.7" horizontal safe margins.
- Slide element overlap ratio must be < 0.2 for any pair of elements.
- API Key remains session-only; never enters SQLite, JSON exports, checkpoints, logs, or LangSmith.
- Every new Pydantic model carries `schema_version=1`.
- Use TDD, minimal code, one focused commit per task.

---

## File Map

- `src/pptmaker/m3/__init__.py`: package init
- `src/pptmaker/m3/models.py`: M3 Pydantic contracts
- `src/pptmaker/m3/design.py`: Design Planner (presets + optional AI)
- `src/pptmaker/m3/content.py`: Content Planner (DesignPlan-informed)
- `src/pptmaker/m3/fonts.py`: font fallback utility
- `src/pptmaker/m3/compiler.py`: deterministic Spec Compiler
- `src/pptmaker/m3/builder.py`: deterministic PPT Builder
- `src/pptmaker/m3/renderer.py`: PowerPoint render adapter
- `src/pptmaker/m3/repository.py`: M3 SQLite persistence
- `src/pptmaker/ui/m3_workspace.py`: Streamlit generation panel
- `scripts/check_m3_gate.py`: M3 acceptance gate
- `scripts/run_m3_evaluation.py`: M3 evaluation harness

---

### Task 1: M3 Domain Contracts

**Files:**
- Create: `src/pptmaker/m3/__init__.py`
- Create: `src/pptmaker/m3/models.py`
- Create: `tests/m3/__init__.py`
- Create: `tests/m3/test_models.py`

**Interfaces:**
- Produces: `SlideContent`, `ContentPlan`, `DesignPlan`, `ColorPalette`, `FontSet`.
- Produces: `TextElement`, `BulletElement`, `ImagePlaceholder`, `RectShape`, `TableBlock`, `SlideElement`, `SlideSpec`.

- [ ] **Step 1: Write failing contract tests**

```python
from pptmaker.m3.models import ContentPlan, DesignPlan, SlideSpec, TextElement

def test_content_plan_carries_schema_version_one():
    plan = ContentPlan(project_id="p1", outline_version=1, slides=[])
    assert plan.schema_version == 1

def test_design_palette_hex_values_are_validated():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ColorPalette(primary="not-a-color", secondary="#fff", accent="#000",
                     background="#fff", text_primary="#000", text_secondary="#666")
```

- [ ] **Step 2: Run focused tests**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m3/test_models.py -v
```

Expected: FAIL because `pptmaker.m3` does not exist.

- [ ] **Step 3: Implement the minimal contracts**

Implement all models defined in the design spec Section 4.2–4.4. Use `pydantic.BaseModel`, `Field` constraints, `Literal` types, and `schema_version` on every top-level model.

- [ ] **Step 4: Run contract tests**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m3/test_models.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/m3 tests/m3/test_models.py
git commit -m "feat: define M3 slide DSL contracts"
```

---

### Task 2: Design Planner (Presets + AI)

**Files:**
- Create: `src/pptmaker/m3/design.py`
- Create: `tests/m3/test_design.py`

**Interfaces:**
- Produces: `PRESETS: dict[str, DesignPlan]` — five built-in presets.
- Produces: `plan_design(brief, style_preset, model, api_key) -> DesignPlan`.

- [ ] **Step 1: Write failing preset and AI tests**

```python
def test_presets_have_valid_contrast():
    for name, plan in PRESETS.items():
        ratio = contrast_ratio(plan.palette.primary, plan.palette.background)
        assert ratio >= 4.5, f"{name} contrast too low"

def test_auto_mode_calls_llm(fake_model):
    plan = plan_design(brief(), "auto", fake_model, "KEY")
    assert plan.preset == "custom"
    assert plan.palette.primary.startswith("#")

def test_business_preset_returns_without_llm():
    plan = plan_design(brief(), "business", None, "")
    assert plan.preset == "business"
    assert "深蓝" in plan.style_notes

def test_invalid_preset_falls_back_to_auto(fake_model):
    plan = plan_design(brief(), "nonexistent", fake_model, "KEY")
    assert plan.preset == "custom"
```

- [ ] **Step 2: Run design tests**

Expected: FAIL — `design.py` missing.

- [ ] **Step 3: Implement presets and AI fallback**

```python
PRESETS = {
    "business": DesignPlan(
        preset="business",
        palette=ColorPalette(primary="#1F4E79", secondary="#5B9BD5", accent="#C59B27",
            background="#FFFFFF", text_primary="#1A1A1A", text_secondary="#666666"),
        fonts=FontSet(title_zh="微软雅黑", body_zh="微软雅黑", title_en="Arial", body_en="Arial",
            title_size=30, subtitle_size=20, body_size=16),
        style_notes="商务专业：深蓝主色搭配金色强调，适合正式汇报场景",
    ),
    # ... academic, creative, minimal, tech presets
}

def plan_design(brief, style_preset, model, api_key):
    if style_preset in PRESETS:
        return PRESETS[style_preset].model_copy(update={"project_id": brief.project_id})
    # "auto" or unknown: call LLM
    result = model.generate(DesignPlan, ..., api_key)
    if not _validate_contrast(result.palette):
        result = _auto_correct_contrast(result)
    return result
```

- [ ] **Step 4: Run tests**

Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/m3/design.py tests/m3/test_design.py
git commit -m "feat: add M3 design presets and AI planner"
```

### Task 3: Content Planner

**Files:**
- Create: `src/pptmaker/m3/content.py`
- Create: `tests/m3/test_content.py`

**Interfaces:**
- Produces: `plan_content(brief, outline, design, chunks, facts, model, api_key) -> ContentPlan`.
- DesignPlan 输入使内容生成感知视觉风格和字号约束。
- 失败时执行一次修复重试，保留缺陷列表供排查。

- [ ] **Step 1: Write failing content tests**

```python
def test_content_covers_all_outline_pages(fake_model):
    outline = outline_with_3_pages()
    plan = plan_content(brief(), outline, design_plan(), [], [], fake_model, "KEY")
    assert len(plan.slides) == 3

def test_content_cites_facts_not_model_memory(fake_model):
    facts = [FactRecord(statement="2026年市场规模500亿", source_title="行业报告", ...)]
    plan = plan_content(brief(), outline(), design_plan(), [], facts, fake_model, "KEY")
    assert "500亿" in plan.slides[0].model_dump_json()

def test_facts_excluded_by_user_are_not_used(fake_model):
    facts = [FactRecord(statement="...", excluded=True, ...)]
    plan = plan_content(brief(), outline(), design_plan(), [], facts, fake_model, "KEY")
    assert facts[0].statement not in plan.model_dump_json()

def test_schema_failure_retries_once_then_fails_recoverable(failing_once_model):
    plan = plan_content(brief(), outline(), design_plan(), [], [], failing_once_model, "KEY")
    assert len(plan.slides) == len(outline.pages)
```

- [ ] **Step 2: Run content tests**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m3/test_content.py -v
```

Expected: FAIL because `content.py` does not exist.

- [ ] **Step 3: Implement the Content Planner**

Call `StructuredModel.generate(ContentPlan, system_prompt, user_prompt, api_key)`. The user prompt includes:

```json
{
  "requirements": brief.model_dump(),
  "outline": outline.model_dump(),
  "materials": [{"source": c.source_name, "text": c.text} for c in chunks],
  "verified_facts": [{"statement": f.statement, "source_title": f.source_title} for f in facts if not f.excluded]
}
```

System prompt instructs: expand each page's title/objective/key_points into full copy; cite verified_facts sources; mark uncertain claims with `[待验证]`; never fabricate data.

Implement the retry-once pattern: catch `StructuredOutputError`, call `model.generate` once more with the defect list, if it fails again raise the safe error.

- [ ] **Step 4: Run tests**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m3/test_content.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/m3/content.py tests/m3/test_content.py
git commit -m "feat: plan M3 slide content from outline"
```

---

### Task 4: Spec Compiler

**Files:**
- Create: `src/pptmaker/m3/compiler.py`
- Create: `tests/m3/test_compiler.py`

**Interfaces:**
- Produces: `compile_specs(content, design) -> list[SlideSpec]`.

- [ ] **Step 1: Write failing layout tests**

```python
def test_all_elements_within_canvas():
    specs = compile_specs(content_plan(), design_plan())
    canvas = Box(0, 0, Inches(13.333), Inches(7.5))
    for spec in specs:
        for element in spec.elements:
            assert not out_of_bounds(element_box(element), canvas)

def test_elements_do_not_severely_overlap():
    specs = compile_specs(content_plan(), design_plan())
    for spec in specs:
        boxes = [element_box(el) for el in spec.elements]
        for i, a in enumerate(boxes):
            for b in boxes[i+1:]:
                assert overlap_ratio(a, b) < 0.2

def test_cover_has_single_centered_title():
    specs = compile_specs(content_plan_with_cover(), design_plan())
    cover = specs[0]
    assert cover.page_type == "cover"
    titles = [e for e in cover.elements if e.type == "text" and e.bold]
    assert len(titles) == 1

def test_content_page_has_title_and_body():
    specs = compile_specs(content_plan_with_content(), design_plan())
    content = next(s for s in specs if s.page_type == "content")
    element_types = {e.type for e in content.elements}
    assert "text" in element_types
```

- [ ] **Step 2: Run compiler tests**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m3/test_compiler.py -v
```

Expected: FAIL because `compiler.py` does not exist.

- [ ] **Step 3: Implement the deterministic Compiler**

Layout rules per page_type:

**cover**: title centered (y=2.5"), subtitle below (y=3.5"), accent line at bottom (y=6.5").
**contents**: numbered list starting at y=1.8", each item with left accent bar, 0.5" spacing.
**section**: large section number (y=2.0") + section title (y=3.5"), full-width accent bar.
**content**: title bar at y=0.3"–1.0", body text at y=1.3"–6.0" with auto-flow. For pages with bullet_points: body text at y=1.3"–3.5", bullets at y=3.8"–6.0". For pages with key_number: large number callout at top-right.
**ending**: centered text at y=2.5"–4.5".

Use the existing M0 `Box` and `out_of_bounds`/`overlap_ratio` from `src/pptmaker/evaluation/geometry.py`. All coordinates in Inches. Wrap in `Inches(value)` calls for python-pptx compatibility.

- [ ] **Step 4: Run tests**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m3/test_compiler.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/m3/compiler.py tests/m3/test_compiler.py
git commit -m "feat: compile M3 slide specs with safe layouts"
```

---

### Task 5: PPT Builder

**Files:**
- Create: `src/pptmaker/m3/builder.py`
- Create: `tests/m3/test_builder.py`

**Interfaces:**
- Produces: `build_pptx(specs, design, output_path) -> Path`.

- [ ] **Step 1: Write failing builder tests**

```python
def test_built_pptx_opens_with_expected_slide_count(tmp_path):
    path = build_pptx(specs_3_pages(), design_plan(), tmp_path / "out.pptx")
    prs = Presentation(path)
    assert len(prs.slides) == 3

def test_pptx_is_16_9(tmp_path):
    path = build_pptx(specs_1_page(), design_plan(), tmp_path / "out.pptx")
    prs = Presentation(path)
    assert prs.slide_width == Inches(13.333)
    assert prs.slide_height == Inches(7.5)

def test_text_is_editable(tmp_path):
    path = build_pptx(specs_with_text(), design_plan(), tmp_path / "out.pptx")
    prs = Presentation(path)
    shapes = prs.slides[0].shapes
    text_shapes = [s for s in shapes if s.has_text_frame]
    assert len(text_shapes) >= 1
    assert text_shapes[0].text_frame.text != ""

def test_builder_outputs_usable_path(tmp_path):
    path = build_pptx(specs_1_page(), design_plan(), tmp_path / "out.pptx")
    assert path.exists()
    assert path.stat().st_size > 0
```

- [ ] **Step 2: Run builder tests**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m3/test_builder.py -v
```

Expected: FAIL because `builder.py` does not exist.

- [ ] **Step 3: Implement the deterministic PPT Builder**

```python
def build_pptx(specs: list[SlideSpec], design: DesignPlan, output_path: Path) -> Path:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    layout = prs.slide_layouts[6]  # blank

    for spec in specs:
        slide = prs.slides.add_slide(layout)
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = hex_to_rgb(spec.background_color)

        for element in spec.elements:
            if element.type == "text":
                box = slide.shapes.add_textbox(
                    Inches(element.x), Inches(element.y),
                    Inches(element.width), Inches(element.height))
                tf = box.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = element.text
                p.font.size = Pt(element.font_size)
                p.font.bold = element.bold
                p.font.color.rgb = hex_to_rgb(element.color)
                p.font.name = element.font_name

            elif element.type == "bullet":
                box = slide.shapes.add_textbox(
                    Inches(element.x), Inches(element.y),
                    Inches(element.width), Inches(element.height))
                tf = box.text_frame
                tf.word_wrap = True
                for i, item in enumerate(element.items):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.text = f"• {item}"
                    p.font.size = Pt(element.font_size)
                    p.font.color.rgb = hex_to_rgb(element.color)
                    p.font.name = element.font_name

            elif element.type == "image_placeholder":
                shape = slide.shapes.add_shape(
                    MSO_AUTO_SHAPE_TYPE.RECTANGLE,
                    Inches(element.x), Inches(element.y),
                    Inches(element.width), Inches(element.height))
                shape.fill.solid()
                shape.fill.fore_color.rgb = hex_to_rgb("#E0E0E0")
                shape.line.color.rgb = hex_to_rgb("#CCCCCC")
                tf = shape.text_frame
                tf.word_wrap = True
                tf.paragraphs[0].text = element.description or "[图片区域]"
                tf.paragraphs[0].font.size = Pt(11)
                tf.paragraphs[0].font.color.rgb = hex_to_rgb("#999999")

            elif element.type == "rect":
                shape = slide.shapes.add_shape(
                    MSO_AUTO_SHAPE_TYPE.RECTANGLE,
                    Inches(element.x), Inches(element.y),
                    Inches(element.width), Inches(element.height))
                shape.fill.solid()
                shape.fill.fore_color.rgb = hex_to_rgb(element.fill_color)
                shape.line.fill.background()

            elif element.type == "table":
                shape = slide.shapes.add_table(
                    len(element.rows), len(element.rows[0]),
                    Inches(element.x), Inches(element.y),
                    Inches(element.width), Inches(element.height))
                for r, row in enumerate(element.rows):
                    for c, cell_text in enumerate(row):
                        shape.table.cell(r, c).text = cell_text

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    return output_path
```

- [ ] **Step 4: Run tests**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m3/test_builder.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/m3/builder.py tests/m3/test_builder.py
git commit -m "feat: build editable pptx from slide specs"
```

---

### Task 6: PowerPoint Renderer

**Files:**
- Create: `src/pptmaker/m3/renderer.py`
- Create: `tests/m3/test_renderer.py`

**Interfaces:**
- Produces: `render_pptx(input_path, output_dir) -> list[Path]`.

- [ ] **Step 1: Write failing renderer tests (office marker)**

```python
@pytest.mark.office
def test_pptx_renders_correct_number_of_images():
    paths = render_pptx(path_to_2_slide_pptx(), tmp_path)
    assert len(paths) == 2
    assert all(p.suffix == ".PNG" for p in paths)

def test_renderer_reuses_m0_client(tmp_path, mocker):
    mock_render = mocker.patch("pptmaker.powerpoint.client.render_with_timeout")
    render_pptx(tmp_path / "test.pptx", tmp_path / "out")
    mock_render.assert_called_once()
```

- [ ] **Step 2: Run renderer tests**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/m3/test_renderer.py -v -m "not office"
```

Expected: non-office tests FAIL; office tests skipped.

- [ ] **Step 3: Implement thin wrapper**

```python
from pptmaker.powerpoint.client import render_with_timeout
from pptmaker.powerpoint.protocol import RenderRequest

def render_pptx(input_path: Path, output_dir: Path) -> list[Path]:
    request = RenderRequest(
        run_id=f"m3-{uuid4().hex[:12]}",
        idempotency_key=f"render-{input_path.stem}",
        input_path=str(input_path.resolve()),
        output_dir=str(output_dir.resolve()),
        control_path=str(output_dir.resolve() / "control.json"),
        cancel_path=str(output_dir.resolve() / "cancel.txt"),
    )
    response = render_with_timeout(request)
    if response.status != "success":
        raise RenderError(response.error or "render failed")
    return [Path(p) for p in response.slide_images]
```

- [ ] **Step 4: Commit**

```powershell
git add src/pptmaker/m3/renderer.py tests/m3/test_renderer.py
git commit -m "feat: wrap M0 PowerPoint renderer for M3"
```

---

### Task 7: M3 Repository

**Files:**
- Create: `src/pptmaker/m3/repository.py`
- Create: `tests/m3/test_m3_repository.py`

**Interfaces:**
- Produces: `M3Repository.save_content/get_content/save_design/get_design/save_specs/get_specs`.

Use the same SQLite JSON-payload pattern as M2.

- [ ] **Step 1: Write failing persistence tests**

```python
def test_content_plan_round_trips(repository):
    plan = ContentPlan(project_id="p1", outline_version=1, slides=[...])
    repository.save_content(plan)
    loaded = repository.get_content("p1", 1)
    assert loaded.slides[0].title == plan.slides[0].title

def test_secrets_not_in_stored_json(repository):
    plan = ContentPlan(project_id="p1", outline_version=1, slides=[])
    repository.save_content(plan)
    db = repository.path.read_bytes()
    assert b"sk-" not in db
    assert b"api_key" not in db.lower()
```

- [ ] **Step 3: Run repository tests**

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add src/pptmaker/m3/repository.py tests/m3/test_m3_repository.py
git commit -m "feat: persist M3 generation artifacts"
```

---

### Task 8: Streamlit M3 Workspace

**Files:**
- Create: `src/pptmaker/ui/m3_workspace.py`
- Modify: `src/pptmaker/ui/m2_workspace.py` (add M3 section after approval)
- Create: `tests/ui/test_m3_workspace.py`

**Interfaces:**
- Produces: `render_m3_generation(project, projects, ...) -> None`.

**Required skill:** Use `developing-with-streamlit` before implementation.

- [ ] **Step 1: Write failing UI smoke tests**

```python
def test_generate_button_appears_after_approval(app_with_approved_outline):
    app = app_with_approved_outline.run()
    assert any(item.label == "生成 PPT" for item in app.button)

def test_download_button_appears_after_generation(app_with_pptx):
    app = app_with_pptx.run()
    assert any("下载 PPTX" in str(item) for item in app.download_button)

def test_thumbnails_display_after_rendering(app_with_renders):
    app = app_with_renders.run()
    assert app.image  # thumbnails rendered
```

- [ ] **Step 2: Run UI tests**

Expected: FAIL because M3 workspace does not exist.

- [ ] **Step 3: Implement the generation panel**

Show after outline is APPROVED:

1. "生成 PPT" primary button.
2. On click: run Content Planner → Design Planner → Spec Compiler → PPT Builder → Renderer, with stage text updates.
3. On success: display thumbnail grid (`st.image`), download button (`st.download_button`).
4. On failure: show safe error message, outline state unchanged.

- [ ] **Step 4: Run tests**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest tests/ui/test_m3_workspace.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/ui/m3_workspace.py src/pptmaker/ui/m2_workspace.py tests/ui/test_m3_workspace.py
git commit -m "feat: add M3 PPT generation workspace"
```

---

### Task 9: M3 Evaluation Gate

**Files:**
- Create: `scripts/check_m3_gate.py`
- Create: `scripts/run_m3_evaluation.py`
- Create: `tests/scripts/test_check_m3_gate.py`
- Create: `tests/fixtures/m3/cases.json`
- Create: `docs/evaluations/m3-gate-report.md`
- Modify: `PPT agent.md`

**Metrics:**
- All non-online/non-office tests pass.
- PPT Builder output opens correctly with python-pptx.
- Element out-of-bounds rate = 0%.
- Severe overlap rate (overlap_ratio ≥ 0.2) = 0%.
- Slide count matches outline page count.
- Text elements are editable in reopened pptx.

- [ ] **Step 1: Write gate tests**

```python
def test_gate_rejects_element_out_of_bounds(tmp_path):
    write_evidence(tmp_path, out_of_bounds_rate=0.01)
    assert "element out of bounds" in check_m3_gate(tmp_path)

def test_gate_rejects_slide_count_mismatch(tmp_path):
    write_evidence(tmp_path, slide_count_match=False)
    assert "slide count mismatch" in check_m3_gate(tmp_path)
```

- [ ] **Step 2: Create evaluation cases**

Three synthetic outline cases in `cases.json`:
- 8-page work report (content-heavy)
- 12-page thesis defense (mixed content/bullets)
- 5-page pitch (cover + 3 content + ending)

Each case includes a complete approved DeckOutline with expected page count.

- [ ] **Step 3: Implement runner and gate**

Runner uses a fake structured model (returning scripted ContentPlan/DesignPlan). It exercises Spec Compiler and PPT Builder with real python-pptx output, then validates geometry, slide count, and text editability.

- [ ] **Step 4: Run complete offline gate**

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest -m "not online and not office" --junitxml=artifacts/m3/pytest.xml -q
C:\Users\DELL\.conda\envs\AI\python.exe scripts/run_m3_evaluation.py
C:\Users\DELL\.conda\envs\AI\python.exe scripts/check_m3_gate.py
```

Expected: all tests PASS and M3 gate exits 0.

- [ ] **Step 5: Manual acceptance**

With DeepSeek Key: create a project, complete interview, approve outline, generate PPT, download and open in PowerPoint.

Verify: file opens without errors, text is editable, no elements are cut off, style matches the topic.

- [ ] **Step 6: Commit**

```powershell
git add scripts/check_m3_gate.py scripts/run_m3_evaluation.py tests/scripts/test_check_m3_gate.py tests/fixtures/m3/cases.json docs/evaluations/m3-gate-report.md "PPT agent.md"
git commit -m "docs: complete M3 generation gate"
```
