# M1 Project Foundation Gate Report

Date: 2026-07-23

## Result

Automated gate: **PASS**

Final human acceptance: **PASS**

## Verified evidence

- Test suite: 149 passed, 1 skipped, 5 Office tests deselected.
- Project persistence: SQLite CRUD, restart persistence, optimistic version checks.
- JSON portability: semantic round-trip with a new UUID; 5 MiB file, 20-level
  nesting, 10,000-key, 1 MiB string, and schema-version limits.
- Secret safety: output-layer logging redaction, fixed Provider errors, no API Key
  in SQLite models, JSON exports, capability reports, or checkpoints.
- Provider boundary: DeepSeek, Kimi, Qwen, and custom OpenAI-compatible presets;
  basic completion, structured output, and tools are probed.
- Workflow recovery: SQLite checkpoint reopened successfully; a terminated child
  process left `RUNNING`, which startup reconciliation changed to
  `FAILED_RECOVERABLE`.
- Streamlit: smoke test and new-session persistence test passed. The project
  survives a new session while the API Key resets to an empty value.
- Machine-readable evidence:
  `artifacts/m1/restart-recovery.json`,
  `artifacts/m1/provider-capabilities.json`, and `artifacts/m1/pytest.xml`.

## Runtime versions

- Python 3.10.20
- Streamlit 1.59.1
- Pydantic 2.13.4
- OpenAI 2.45.0
- LangGraph 1.2.9
- langgraph-checkpoint-sqlite 3.1.0

## Human acceptance

The user confirmed:

- DeepSeek runtime connection and capability probing succeeded;
- project creation, JSON export/import, and confirmed deletion worked;
- exact duplicate creation/import was rejected;
- refreshing cleared the API Key while persisted project data remained.

The explicit pytest DeepSeek test skipped because `DEEPSEEK_API_KEY` was absent
from the automated test process. The successful UI probe provides the M1 online
acceptance evidence. No Key was read from chat or written to disk.

## Known limitations

- Claude native API is not supported by the OpenAI-compatible adapter.
- Vision and maximum context remain `unknown` unless reliable Provider metadata
  becomes available.
- API Keys and current UI state are intentionally lost with the Streamlit session.
- The existing `datasets 5.0.0` / `fsspec 2026.6.0` environment warning predates
  M1; M1 introduced no additional dependency conflict.
- Office integration tests require an interactive Windows login session. M0 Office
  acceptance remains the applicable evidence.

## M2 entry criteria

M1 entry requirements for M2 are satisfied. M2 may consume project IDs, session
Provider configuration, safe capability reports, and LangGraph checkpoints; it
must not persist API Keys.
