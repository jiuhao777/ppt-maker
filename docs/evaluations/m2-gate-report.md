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

- 197 tests passed;
- 6 tests deselected: external DeepSeek and interactive Office tests;
- M2 automated gate passed;
- key-field coverage: 100%;
- invalid-question rate: 0%;
- mean interview turns: 2.25;
- research-task traceability: 100%;
- outline-version accuracy: 100%;
- approval violations: 0;
- secret leaks: 0.

The four evaluation cases are isolated synthetic cases: topic only, sufficient material, insufficient material with unknown answers, and mixed-file input.

## Implemented scope

- safe Markdown, DOCX, text PDF, and PPTX ingestion;
- explicit image and scanned-PDF unsupported state;
- confidence-aware requirement extraction and single-question interviews;
- question reasons, confirmed-information summary, and unknown assumptions;
- versioned editable outlines with stable page IDs and comparison data;
- deterministic reflection and one bounded correction;
- research tasks for every unresolved outline gap;
- LangGraph question and approval interrupts with SQLite checkpoints;
- restart recovery without persisted API Keys;
- Streamlit task, interview, outline, version, restore, and approval controls.

## Manual acceptance still required

Run the app from a console that has the runtime DeepSeek Key:

```powershell
streamlit run src/pptmaker/ui/app.py
```

Verify:

1. create a project and enter a Chinese topic;
2. receive relevant questions with reasons and no repeated known field;
3. use “不知道/不确定” once and confirm the assumption is visible;
4. generate an outline, edit it, save a new version, and inspect the difference;
5. approve the exact version and confirm research-task count appears;
6. refresh and confirm project state remains while the API Key is cleared.

No Key is written to the database, checkpoint, JSON export, evaluation artifact, or log.

## Known limitations

- M2 does not perform web research; it only produces research-task contracts.
- Images and scanned PDFs are not recognized until the later visual milestone.
- Full page copy, SlideDSL, PPTX generation, and rendering are outside M2.
- Playwright CLI could not retain a browser/server process inside the current non-interactive Codex Windows session. Streamlit AppTest passed; user-browser acceptance remains the authoritative visual check.
