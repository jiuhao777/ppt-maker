# P0 Reliability Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the confirmed M2/M3 crashes, invalid context truncation, rework-scope regressions, unsafe model errors, and false-positive M3 gate before adding new product capabilities.

**Architecture:** Keep the current M2/M3 boundaries. Normalize model vocabulary before compilation, build bounded context as valid Python structures before JSON serialization, distinguish global reporting from scope-blocking rework defects, and make the M3 evaluator exercise every currently supported layout.

**Tech Stack:** Python 3.10.20 local environment, Pydantic 2, pytest, Streamlit AppTest, python-pptx, existing SQLite repositories.

## Global Constraints

- Write the smallest code that closes a failing test.
- Do not introduce the Deck Blueprint, image providers, or new layouts in P0.
- API keys and raw provider responses must never enter UI errors, logs, files, SQLite, or test snapshots.
- Local rework must preserve every page outside `impact.impacted_page_ids`.
- All model user payloads must remain valid JSON after context limiting.
- Every task ends with focused tests and an independent commit.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/pptmaker/m2/models.py` | Typed requirement values and M2 contracts |
| `src/pptmaker/m2/outlines.py` | Outline context building and quality reflection |
| `src/pptmaker/m2/rework.py` | Impact analysis, scoped rework, retry preservation |
| `src/pptmaker/m3/models.py` | M3 content and SlideDSL validation |
| `src/pptmaker/m3/compiler.py` | Page/layout normalization and deterministic compilation |
| `src/pptmaker/m3/content.py` | Bounded valid content-planner evidence |
| `src/pptmaker/providers/structured.py` | Safe structured-output retry and errors |
| `src/pptmaker/ui/m2_workspace.py` | Safe M2 user-facing errors |
| `src/pptmaker/ui/m3_workspace.py` | Safe M3 user-facing errors |
| `scripts/run_m3_evaluation.py` | Representative M3 machine-readable evaluation |
| `scripts/check_m3_gate.py` | Gate requirements for representative evaluation |

### Task 1: Repair M3 Page and Layout Contracts

**Files:**
- Modify: `src/pptmaker/m3/models.py`
- Modify: `src/pptmaker/m3/compiler.py`
- Modify: `tests/m3/test_models.py`
- Modify: `tests/m3/test_compiler.py`

**Interfaces:**
- Consumes: `SlideContent.page_type`, `SlideContent.layout`
- Produces: `normalize_page_type(value: str) -> str`, `normalize_layout(value: str) -> str`, valid `SlideSpec[]`

- [ ] **Step 1: Add failing model and compiler tests**

```python
import pytest

from pptmaker.m3.compiler import compile_specs, normalize_layout, normalize_page_type
from pptmaker.m3.models import TableBlock


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("封面", "cover"),
        ("目录", "contents"),
        ("章节过渡", "section"),
        ("内容", "content"),
        ("数据", "content"),
        ("案例", "content"),
        ("金句", "content"),
        ("结尾", "ending"),
    ],
)
def test_page_type_aliases_are_normalized(raw, expected):
    assert normalize_page_type(raw) == expected


def test_section_uses_compiler_order():
    spec = compile_specs(
        _content([_page("s", 1, "第一章", page_type="章节过渡")]),
        _design(),
    )[0]
    assert spec.page_type == "section"
    assert any(element.type == "text" and element.text == "1" for element in spec.elements)


def test_table_layout_compiles_table_block():
    spec = compile_specs(
        _content([
            _page(
                "t",
                1,
                "对比结果",
                layout="table",
                table_rows=[["项目", "结果"], ["A", "10"]],
            )
        ]),
        _design(),
    )[0]
    assert any(isinstance(element, TableBlock) for element in spec.elements)


def test_unknown_layout_falls_back_to_text():
    assert normalize_layout("unknown-from-model") == "text"
```

- [ ] **Step 2: Run the tests and verify the confirmed failures**

Run:

```powershell
conda run -n AI python -m pytest tests/m3/test_models.py tests/m3/test_compiler.py -q
```

Expected: failures include missing normalization, section `AttributeError`, and table `NameError`.

- [ ] **Step 3: Implement minimal normalization and compiler fixes**

Add to `src/pptmaker/m3/compiler.py`:

```python
from pptmaker.m3.models import TableBlock


PAGE_TYPE_ALIASES = {
    "封面": "cover",
    "目录": "contents",
    "章节": "section",
    "章节过渡": "section",
    "内容": "content",
    "数据": "content",
    "案例": "content",
    "金句": "content",
    "结尾": "ending",
}
VALID_LAYOUTS = {
    "text",
    "bullets",
    "two_column",
    "big_number",
    "comparison",
    "table",
    "quote",
}


def normalize_page_type(value: str) -> str:
    normalized = value.strip().lower()
    return PAGE_TYPE_ALIASES.get(normalized, normalized)


def normalize_layout(value: str) -> str:
    normalized = value.strip().lower()
    return normalized if normalized in VALID_LAYOUTS else "text"
```

In `_compile_slide`, normalize once and pass `order` into `_section`:

```python
page_type = normalize_page_type(slide.page_type)
layout = normalize_layout(slide.layout)

if page_type == "section":
    elements = _section(slide, order, font, design)
```

Change the section signature and section number:

```python
def _section(slide: SlideContent, order: int, font, design) -> list:
    return [
        _text(str(order), MARGIN_X, 2.0, 3.0, 1.2,
              font.title_size + 12, font.title_zh, bold=True),
        _text(slide.title, MARGIN_X, 3.5, CANVAS_W - 2 * MARGIN_X, 0.8,
              font.title_size, font.title_zh, bold=True),
        RectShape(type="rect", x=MARGIN_X, y=4.8,
                  width=CANVAS_W - 2 * MARGIN_X, height=0.03,
                  fill_color=design.palette.accent),
    ]
```

Return the normalized type in `SlideSpec.page_type` and replace the chained conditional layout expression with a small mapping:

```python
handlers = {
    "text": _content,
    "bullets": _bullets_layout,
    "two_column": _two_column,
    "big_number": _big_number,
    "comparison": _comparison,
    "table": _table_layout,
    "quote": _quote_layout,
}
elements = handlers[layout](slide, font, design)
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
conda run -n AI python -m pytest tests/m3/test_models.py tests/m3/test_compiler.py -q
```

Expected: all focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/m3/models.py src/pptmaker/m3/compiler.py tests/m3/test_models.py tests/m3/test_compiler.py
git commit -m "fix: normalize and compile m3 page contracts"
```

### Task 2: Preserve Valid JSON Under Context Limits

**Files:**
- Modify: `src/pptmaker/m2/outlines.py`
- Modify: `src/pptmaker/m2/rework.py`
- Modify: `src/pptmaker/m3/content.py`
- Modify: `tests/m2/test_outline_services.py`
- Modify: `tests/m2/test_rework.py`
- Modify: `tests/m3/test_content.py`

**Interfaces:**
- Consumes: requirements, material chunks, facts, outlines, rework impacts
- Produces: complete JSON documents with bounded list entries

- [ ] **Step 1: Add failing context-integrity tests**

Use each module's existing fake model to capture the `user` argument and add:

```python
def test_outline_prompt_is_valid_json_with_large_material():
    model = CapturingModel(valid_outline_draft())
    generate_outline(
        brief(),
        [chunk(text="中" * 200_000)],
        model,
        "TEST_KEY",
    )
    payload = json.loads(model.calls[0]["user"])
    assert len(payload["materials"]) == 1
    assert len(payload["materials"][0]["text"]) <= 3_000


def test_rework_payload_is_valid_json_with_large_outline():
    model = CapturingModel(valid_impact())
    analyze_rework(large_outline(), local_request(), model, "TEST_KEY")
    json.loads(model.calls[0]["user"])


def test_content_payload_is_valid_json_with_large_evidence():
    model = CapturingModel(valid_content_plan())
    plan_content(
        project_id="p1",
        outline=large_outline(),
        brief=brief(),
        chunks=[chunk(text="中" * 200_000)],
        facts=[],
        design=design(),
        model=model,
        api_key="TEST_KEY",
    )
    json.loads(model.calls[0]["user"])
```

- [ ] **Step 2: Verify tests fail because serialized JSON is sliced**

Run:

```powershell
conda run -n AI python -m pytest tests/m2/test_outline_services.py tests/m2/test_rework.py tests/m3/test_content.py -q
```

Expected: at least one `JSONDecodeError`.

- [ ] **Step 3: Bound structures before serialization**

In all three modules:

- keep at most 10 material chunks;
- keep at most 100 active facts;
- truncate each material text to 3,000 characters;
- truncate fact statements and titles to their model field limits;
- serialize only after constructing the bounded dictionary;
- remove all `json.dumps(... )[:N]` expressions.

The outline material expression becomes:

```python
"materials": [
    {
        "source": chunk.source_name,
        "location": chunk.location,
        "text": chunk.text[:3_000],
    }
    for chunk in chunks[:10]
],
```

The fact expression becomes:

```python
"verified_facts": [
    {
        "statement": fact.statement[:2_000],
        "source_url": str(fact.source_url),
        "source_title": fact.source_title[:500],
    }
    for fact in (facts or [])
    if not fact.excluded
][:100],
```

Serialize without slicing:

```python
prompt = json.dumps(evidence, ensure_ascii=False)
```

The rework retry payload must retain `impact` and the original outline:

```python
retry_payload = {
    "current_outline": current.model_dump(mode="json"),
    "impact": impact.model_dump(mode="json"),
    "candidate": candidate.model_dump(mode="json"),
    "defects": reflection.defects,
}
```

- [ ] **Step 4: Run focused tests**

Run the Step 2 command.

Expected: all focused tests pass and every captured model payload parses with `json.loads`.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/m2/outlines.py src/pptmaker/m2/rework.py src/pptmaker/m3/content.py tests/m2/test_outline_services.py tests/m2/test_rework.py tests/m3/test_content.py
git commit -m "fix: keep model context structurally valid"
```

### Task 3: Restore Numeric Requirements and Scoped Reflection

**Files:**
- Modify: `src/pptmaker/m2/outlines.py`
- Modify: `src/pptmaker/m2/rework.py`
- Modify: `tests/m2/test_outline_services.py`
- Modify: `tests/m2/test_rework.py`

**Interfaces:**
- Produces: `_positive_int(value: str | None) -> int | None`
- Produces: scope-blocking defects that only inspect impacted pages

- [ ] **Step 1: Add failing numeric and local-scope tests**

```python
def test_string_page_count_is_checked():
    value = brief(target_slides="12")
    outline = valid_outline(target_slides=10)
    assert "requested_page_count_mismatch" in reflect_outline(value, outline).defects


def test_string_duration_is_checked():
    value = brief(duration_minutes="5")
    outline = valid_outline(target_slides=12)
    assert "duration_density_high" in reflect_outline(value, outline).defects


def test_local_reflection_ignores_unrelated_duplicate_and_numeric_pages():
    outline = outline_with_unrelated_global_defects()
    result = reflect_outline(
        brief(),
        outline,
        scope_page_ids={outline.pages[-1].id},
    )
    assert result.passed


def test_rework_retry_preserves_scope_instructions():
    model = CapturingModel([invalid_local_draft(), corrected_local_draft()])
    apply_rework(current(), brief(), [], local_impact(), model, "TEST_KEY")
    retry = model.calls[1]
    assert "影响范围外" in retry["system"]
    assert json.loads(retry["user"])["impact"]["mode"] == "local"
```

- [ ] **Step 2: Run tests and verify failures**

Run:

```powershell
conda run -n AI python -m pytest tests/m2/test_outline_services.py tests/m2/test_rework.py -q
```

Expected: numeric requirement checks and local reflection tests fail.

- [ ] **Step 3: Parse numeric requirement strings**

Add:

```python
def _positive_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value.strip())
    except (AttributeError, TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
```

Replace the two `isinstance(..., int)` checks:

```python
requested = _positive_int(brief.target_slides.value)
duration = _positive_int(brief.duration_minutes.value)
```

- [ ] **Step 4: Separate global reporting from scoped blocking**

When `scope_page_ids` is not `None`, calculate page-derived defects only from `pages_to_check`. Do not add `duplicate_titles`, `unsupported_numeric_fact`, `title_too_long`, or `too_many_key_points` from pages outside the scope. Keep structural corruption checks (`page_count_mismatch` and `page_order_invalid`) global because a valid local draft cannot alter page identity or order.

Update the retry system prompt:

```python
(
    f"修正以下缺陷：{', '.join(reflection.defects)}。"
    "严格遵守 impact；局部返工必须逐字保留影响范围外页面及其页面 ID。"
    "不得增加、删除或重排范围外页面。"
)
```

- [ ] **Step 5: Run focused tests**

Run the Step 2 command.

Expected: all focused tests pass.

- [ ] **Step 6: Commit**

```powershell
git add src/pptmaker/m2/outlines.py src/pptmaker/m2/rework.py tests/m2/test_outline_services.py tests/m2/test_rework.py
git commit -m "fix: restore requirement and scoped rework checks"
```

### Task 4: Prevent Provider Response Leakage

**Files:**
- Modify: `src/pptmaker/providers/structured.py`
- Modify: `src/pptmaker/ui/m2_workspace.py`
- Modify: `src/pptmaker/ui/m3_workspace.py`
- Modify: `tests/providers/test_structured.py`
- Modify: `tests/ui/test_m2_workspace.py`
- Create: `tests/ui/test_m3_workspace.py`

**Interfaces:**
- Produces: safe `StructuredOutputError(category, message)`
- Produces: fixed user messages by safe category

- [ ] **Step 1: Add failing secret-response and UI tests**

```python
def test_invalid_model_content_is_not_exposed():
    secret = "private material sk-123456"
    client = FakeFactory([secret, secret, secret])
    with pytest.raises(StructuredOutputError) as error:
        StructuredModel(CONFIG, client).generate(
            Answer, "system", "user", "TEST_KEY"
        )
    assert secret not in str(error.value)
    assert "sk-" not in str(error.value)


def test_m3_unexpected_error_uses_generic_message(monkeypatch):
    monkeypatch.setattr(
        "pptmaker.ui.m3_workspace.build_presentation",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("C:\\private\\project sk-123")
        ),
    )
    app = run_m3_app_test()
    assert "sk-123" not in "\n".join(error.value for error in app.error)
    assert "生成失败，请重试" in "\n".join(error.value for error in app.error)
```

- [ ] **Step 2: Verify tests fail**

Run:

```powershell
conda run -n AI python -m pytest tests/providers/test_structured.py tests/ui/test_m2_workspace.py tests/ui/test_m3_workspace.py -q
```

Expected: raw model content or raw exception text appears.

- [ ] **Step 3: Remove raw response snippets**

In `StructuredModel.generate`, keep field names for Pydantic validation failures but remove all `content[:200]` text:

```python
elif content is None:
    msg += "（API 返回内容为空）"
else:
    msg += "（返回内容无法解析）"
```

In M2 and M3 UI, map known safe categories and use a generic fallback:

```python
SAFE_PROVIDER_MESSAGES = {
    "authentication": "API Key 无效或无权访问该模型。",
    "rate_limit": "模型服务请求过于频繁，请稍后重试。",
    "timeout": "模型服务响应超时，请重试。",
    "invalid_structure": "模型未返回有效结构化结果，请重试。",
}


def _safe_generation_message(exc: Exception) -> str:
    if isinstance(exc, StructuredOutputError):
        return SAFE_PROVIDER_MESSAGES.get(exc.category, "模型服务暂时不可用。")
    return "生成失败，请重试。"
```

Never render `str(exc)` for unexpected exceptions.

- [ ] **Step 4: Run focused tests**

Run the Step 2 command.

Expected: all focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/pptmaker/providers/structured.py src/pptmaker/ui/m2_workspace.py src/pptmaker/ui/m3_workspace.py tests/providers/test_structured.py tests/ui/test_m2_workspace.py tests/ui/test_m3_workspace.py
git commit -m "fix: keep provider responses out of user errors"
```

### Task 5: Make the M3 Evaluation Representative

**Files:**
- Modify: `scripts/run_m3_evaluation.py`
- Modify: `scripts/check_m3_gate.py`
- Create: `tests/m3/test_m3_evaluation.py`
- Create: `tests/fixtures/m3/layout_matrix.json`

**Interfaces:**
- Produces: `artifacts/m3/evaluation.json`
- Gate requires each supported layout and page type to be exercised successfully

- [ ] **Step 1: Add the layout matrix fixture**

The fixture contains one page for each current contract:

```json
{
  "project_id": "m3-layout-matrix",
  "slides": [
    {"page_id":"cover","page_type":"cover","layout":"text","title":"封面"},
    {"page_id":"contents","page_type":"contents","layout":"text","title":"目录","bullet_points":["一","二"]},
    {"page_id":"section","page_type":"章节过渡","layout":"text","title":"第一章"},
    {"page_id":"text","page_type":"content","layout":"text","title":"结论页","body_paragraphs":["正文"]},
    {"page_id":"bullets","page_type":"content","layout":"bullets","title":"要点","bullet_points":["A","B"]},
    {"page_id":"columns","page_type":"content","layout":"two_column","title":"双栏","body_paragraphs":["左"],"bullet_points":["右"]},
    {"page_id":"number","page_type":"数据","layout":"big_number","title":"核心数字","body_paragraphs":["83%","增长率"]},
    {"page_id":"comparison","page_type":"content","layout":"comparison","title":"对比","bullet_points":["A","B"]},
    {"page_id":"table","page_type":"content","layout":"table","title":"表格","table_rows":[["项目","值"],["A","10"]]},
    {"page_id":"quote","page_type":"金句","layout":"quote","title":"金句","body_paragraphs":["保持简单"]},
    {"page_id":"ending","page_type":"结尾","layout":"text","title":"谢谢"}
  ]
}
```

- [ ] **Step 2: Add a failing evaluation contract test**

```python
def test_evaluation_covers_every_supported_contract(tmp_path):
    report = evaluate(load_layout_matrix(), output_dir=tmp_path)
    assert report["crashes"] == []
    assert set(report["layouts_exercised"]) == {
        "text", "bullets", "two_column", "big_number",
        "comparison", "table", "quote",
    }
    assert {"cover", "contents", "section", "content", "ending"} <= set(
        report["page_types_exercised"]
    )
```

- [ ] **Step 3: Verify the evaluator fails on the current single-layout implementation**

Run:

```powershell
conda run -n AI python -m pytest tests/m3/test_m3_evaluation.py -q
```

Expected: missing coverage fields or compile crash.

- [ ] **Step 4: Extend the evaluator and gate**

The evaluator must record:

```python
{
    "cases": len(cases),
    "layouts_exercised": sorted(layouts),
    "page_types_exercised": sorted(page_types),
    "crashes": crashes,
    "slide_count_match": slide_count_match,
    "out_of_bounds_rate": out_of_bounds_rate,
    "severe_overlap_rate": severe_overlap_rate,
    "text_editable": text_editable,
    "secret_leaks": secret_leaks,
}
```

The gate fails when:

```python
required_layouts - set(report["layouts_exercised"])
or required_page_types - set(report["page_types_exercised"])
or report["crashes"]
or not report["slide_count_match"]
or report["out_of_bounds_rate"] != 0
or report["severe_overlap_rate"] != 0
or not report["text_editable"]
or report["secret_leaks"] != 0
```

- [ ] **Step 5: Run evaluator and gate**

Run:

```powershell
conda run -n AI python -m pytest tests/m3/test_m3_evaluation.py -q
conda run -n AI python scripts/run_m3_evaluation.py
conda run -n AI python scripts/check_m3_gate.py
```

Expected: test and gate pass; the JSON report lists every supported contract.

- [ ] **Step 6: Commit**

```powershell
git add scripts/run_m3_evaluation.py scripts/check_m3_gate.py tests/m3/test_m3_evaluation.py tests/fixtures/m3/layout_matrix.json
git commit -m "test: make m3 gate cover every layout"
```

### Task 6: P0 Regression and Evidence Closure

**Files:**
- Modify only if generated by the existing scripts: `docs/evaluations/m3-gate-report.md`
- Do not modify M0 evidence by hand.

**Interfaces:**
- Consumes: all P0 changes
- Produces: passing offline suite and M1–M3 automated gates

- [ ] **Step 1: Run the complete offline suite**

```powershell
conda run -n AI python -m pytest -m "not online and not office" -q
```

Expected: all collected tests pass.

- [ ] **Step 2: Run automated gates**

```powershell
conda run -n AI python scripts/check_m1_gate.py
conda run -n AI python scripts/check_m2_gate.py
conda run -n AI python scripts/run_m3_evaluation.py
conda run -n AI python scripts/check_m3_gate.py
```

Expected: M1, M2, and M3 gates exit `0`.

- [ ] **Step 3: Record the M0 evidence limitation**

Run:

```powershell
conda run -n AI python scripts/check_m0_gate.py
```

Expected before regeneration: stale-fingerprint failures remain explicit. Do not claim M0 passed until Office, security, parser, and DeepSeek probes are rerun from current source.

- [ ] **Step 4: Check for accidental scope and secret changes**

```powershell
git diff --check
git status --short
rg -n "sk-[A-Za-z0-9_-]{8,}|Bearer\\s+[A-Za-z0-9._-]+" src tests docs
```

Expected: no whitespace errors, only intended files changed, and no real-looking keys.

- [ ] **Step 5: Commit generated P0 evidence if changed**

```powershell
git add docs/evaluations/m3-gate-report.md
git commit -m "test: close p0 reliability gate"
```

Skip the commit when the report file is unchanged.

