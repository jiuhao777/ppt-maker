# M2 Requirements and Outline Gate Report

## Result

Automated gate: **PASS**

Manual DeepSeek and user-browser acceptance: **PENDING**

M2 implementation is complete, but formal milestone acceptance remains pending until the user runs one real DeepSeek topic case and confirms the local Streamlit flow.

## Automated evidence

Command:

```powershell
C:\Users\DELL\.conda\envs\AI\python.exe -m pytest -m "not online and not office" --junitxml=artifacts/m2/pytest.xml -q
C:\Users\DELL\.conda\envs\AI\python.exe scripts/run_m2_evaluation.py
C:\Users\DELL\.conda\envs\AI\python.exe scripts/check_m2_gate.py
```

Results:

- 256 tests passed;
- 6 tests deselected: external DeepSeek and interactive Office tests;
- M2 automated gate passed;
- key-field coverage: 100%;
- invalid-question rate: 0%;
- mean interview turns: 2.25;
- maximum interview turns: 5;
- task-specific question variation: 100%;
- research-task traceability: 100%;
- research-task deduplication: 100%;
- local rework scope accuracy: 100%;
- outline-version accuracy: 100%;
- new-version auto-selection: 100%;
- freshness-route accuracy: 100%;
- user-policy override accuracy: 100%;
- normalized-fact traceability: 100%;
- unsafe-content rejection: 100%;
- approval violations: 0;
- secret leaks: 0.

The four evaluation cases are isolated synthetic cases: topic only, sufficient material, insufficient material with unknown answers, and mixed-file input.

## Implemented scope

- safe Markdown, DOCX, text PDF, and PPTX ingestion;
- explicit image and scanned-PDF unsupported state;
- confidence-aware requirement extraction and single-question interviews;
- concise task-aware questions with choices, normally 3–6 and never above 8;
- question reasons, confirmed-information summary, and unknown assumptions;
- two-stage global/local AI rework with confirmed impact scope;
- versioned editable outlines with stable page IDs, metadata, auto-selection, and comparison data;
- deterministic reflection and one bounded correction;
- deduplicated research tasks for every unresolved outline gap;
- LangGraph question and approval interrupts with SQLite checkpoints;
- restart recovery without persisted API Keys;
- Streamlit task, interview, outline, version, restore, and approval controls.
- three-state web policy with an AI-assisted deterministic freshness router;
- session-only optional Bocha Key and fixed-endpoint search adapter;
- normalized project Fact Store with source exclusion;
- current facts supplied to outline generation with URLs and access dates.

## Manual acceptance still required

Run the app from a console that has the runtime DeepSeek Key:

```powershell
streamlit run src/pptmaker/ui/app.py
```

Verify:

1. configure a runtime DeepSeek Key and optional Bocha Key;
2. select `AUTO`, enter “中国大模型现状”, and confirm web verification runs with dated sources;
3. upload a quarterly report for summarization and confirm `AUTO` does not search;
4. select `ALWAYS` without a Bocha Key and confirm the warning and disabled action;
5. select `NEVER` for a current topic and confirm the freshness-risk warning;
6. exclude one source and confirm regeneration no longer receives that fact;
7. receive concise task-relevant questions and complete global/local rework;
8. refresh and confirm both Keys are cleared while policy, facts, and versions remain.

No Key is written to the database, checkpoint, JSON export, evaluation artifact, or log.

## Known limitations

- M2 performs only bounded freshness verification; full data, case, image, and citation research remains a later milestone.
- Images and scanned PDFs are not recognized until the later visual milestone.
- Full page copy, SlideDSL, PPTX generation, and rendering are outside M2.
- Playwright CLI could not retain a browser/server process inside the current non-interactive Codex Windows session. Streamlit AppTest passed; user-browser acceptance remains the authoritative visual check.
