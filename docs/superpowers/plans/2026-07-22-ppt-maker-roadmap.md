# PPT-maker Implementation Roadmap

> **For agentic workers:** Each phase requires its own implementation plan and must pass its gate before the next phase is planned in detail.

**Goal:** Deliver a high-quality local Windows PPT Agent through testable vertical slices without building speculative infrastructure.

**Architecture:** A React/FastAPI local product uses LangGraph for durable workflow execution and a progressively built Agent Harness for model/tool reliability. PowerPoint COM and local vision inference run in isolated workers; `ProjectState + DeckBible + SlideDSL` remain the source of truth.

**Tech Stack:** Python 3.10.20, Conda `AI`, FastAPI, Pydantic, LangChain, LangGraph, SQLite, python-pptx, pywin32, React, TypeScript, PowerPoint, pytest, Playwright.

## Global Constraints

- Target only Windows 11 with Microsoft PowerPoint installed.
- Run Python commands through `conda run -n AI`.
- Use `npm.cmd` on this machine because PowerShell blocks `npm.ps1`.
- Keep API keys outside project files, logs, traces, fixtures, and exports.
- Treat uploads, webpages, downloaded assets, and model output as untrusted input.
- Never execute macros, OLE objects, downloaded scripts, or webpage instructions.
- `ProjectState + DeckBible + SlideDSL` are authoritative; `.pptx` is an artifact.
- Every phase ends with automated tests, a written evaluation report, and a human review gate.
- Do not commit `models/`, local project data, secrets, generated decks, or downloaded test assets.

## Phase Sequence

| Phase | Working deliverable | Gate |
|---|---|---|
| M0 | Technical probes and measured risk report | PowerPoint generation/rendering, security, DeepSeek schema, parsers, and vision candidates have reproducible results |
| M1 | Minimal text-to-PPT vertical slice | Browser input produces and renders a real editable project-report deck |
| M2 | Minimum Harness around the working slice | Provider contract, schema validation, retry, run IDs, local traces, secrets, project store, and SQLite checkpoints pass recovery tests |
| M3 | Complete project-report workflow | Requirement interview, outline approval, DeckBible, 6–10 slides, preview, pause/resume, and human acceptance work end to end |
| M4 | Secure document ingestion and retrieval | Word/PDF/PPT/image inputs preserve source locations and pass security/challenge suites |
| M5 | Online research and licensed assets | Keyed search, manual URLs, Fact Store, safe/wide image modes, and source manifest pass provenance tests |
| M6 | Design system, samples, and templates | Sample approval, design tokens, layout selection, theme inheritance, components, and simple animation pass render regression |
| M7 | Evaluation, reflection, and repair | Rule/content/vision evaluators and bounded repair reduce target defects without new severe defects |
| M8 | Natural-language editing and versions | EditPlan, locks, incremental rebuild, undo, rollback, and version comparison preserve unaffected pages |
| M9 | Additional task modes | Each mode has distinct requirements, narrative policy, prompts, and benchmark cases |
| M10 | Frozen evaluation and open-source package | Test-set report, blind review, ablations, traces, docs, license inventory, and demo assets are reproducible |

## Planning Rule

Only M0 is planned at task-level now. At each gate, record measured constraints in an ADR, update this roadmap if necessary, and create the next phase plan. This prevents parser, search, VLM, packaging, and Harness choices from being fixed before evidence exists.

