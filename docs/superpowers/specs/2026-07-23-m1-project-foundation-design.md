# M1 Project Foundation Design

## Goal

Build the smallest usable local workspace that can create, persist, restore,
export, import, and delete PPT Agent projects, while safely testing an
OpenAI-compatible model Provider.

## Scope

M1 includes:

- a local Streamlit workspace;
- SQLite project persistence;
- project JSON export and import;
- in-memory API Key handling;
- OpenAI-compatible Provider configuration and connection testing;
- a minimal LangGraph checkpoint path;
- redacted logs and user-facing errors.

M1 does not generate outlines, slides, images, research results, or PPTX files.
Those capabilities begin in later milestones.

## User Flow

The start page lists projects ordered by most recently updated. The user can:

1. create a project by entering a name;
2. open an existing project;
3. delete a project after explicit confirmation;
4. export one project as JSON;
5. import a valid project JSON as a new project.

Inside a project, the user selects a Provider preset or custom
OpenAI-compatible configuration, enters an API Key in a password field, and
tests the connection. The Key remains only in the current Streamlit session.
After application restart the project remains, but the Key field is empty.

## UI

Streamlit is used because the product is local, form-driven, and
workspace-oriented.

The interface has two views:

- Project list: project cards, create, import, delete, and last-updated time.
- Project workspace: project summary, Provider configuration, connection
  status, and JSON export.

The first version uses Streamlit's native components and a small theme file.
It does not add custom JavaScript, a component framework, or decorative
animations.

## Persistence

SQLite is the system of record. The database is
`%LOCALAPPDATA%\PPTMaker\pptmaker.db`, not a file in the Git repository.

The `projects` table stores:

- UUID project ID;
- name;
- schema version;
- business state;
- execution state;
- persisted project payload;
- creation and update timestamps.

Business state and execution state are separate. M1 uses:

- business state: `DRAFT`;
- execution state: `IDLE`, `RUNNING`, `WAITING_FOR_USER`, `PAUSED`,
  `CANCELLING`, `CANCELLED`, `FAILED_RECOVERABLE`, `FAILED_FINAL`,
  `COMPLETED`.

Provider metadata persists:

- Provider type;
- Base URL;
- model name.

API Keys never persist.

SQLite operations use explicit transactions. Project updates use optimistic
version checks so a stale UI session cannot silently overwrite newer state.

## JSON Portability

Exported JSON contains:

- export schema version;
- project ID and name;
- project state;
- Provider type, Base URL, and model;
- creation and update timestamps.

It never contains API Keys, logs, absolute local paths, or LangGraph internal
database rows.

Import rejects files larger than 5 MiB and validates the complete schema before writing. Imported
projects receive a new project ID to avoid overwriting an existing project.
Unknown schema versions fail with a clear message.

## Provider Boundary

M1 implements one `OpenAICompatibleProvider` using the OpenAI Python client.
It supports configurable Base URL and model name.

Presets only supply defaults:

- DeepSeek;
- Kimi;
- Alibaba Cloud Model Studio;
- Custom OpenAI-compatible.

Claude is displayed as unsupported by this adapter because its native API is
not OpenAI-compatible. A dedicated adapter can be added later without changing
project persistence.

Connection testing sends one minimal structured request and validates the
response. It reports:

- success;
- authentication failure;
- rate limit;
- timeout/network failure;
- unsupported endpoint or model.

The response body is not persisted.

## API Key Safety

The API Key enters through a password field and is stored only in
`st.session_state`. It is passed directly to the Provider client for the
current request.

The following boundaries reject or redact secret-like values:

- SQLite writes;
- JSON export;
- application logs;
- exception rendering;
- LangSmith metadata;
- test snapshots.

Development tests may read `DEEPSEEK_API_KEY` from the current process
environment. Tests never write it to disk or echo it.

## LangGraph Checkpoint

M1 includes a minimal graph with one deterministic state transition and an
SQLite-backed checkpoint. Its purpose is to prove that a project can resume
after process restart.

The graph state stores project identifiers and non-secret workflow data only.
Provider clients and API Keys are runtime dependencies and never enter graph
state.

## Errors and Recovery

- Invalid import: reject before database mutation.
- Duplicate project name: allowed; project ID is authoritative.
- Stale project update: reject and ask the UI to reload.
- Provider failure: keep the project unchanged and show a categorized error.
- Database failure: roll back the transaction and show a recoverable error.
- Missing API Key: disable connection testing and explain what is required.

No exception shown to the user includes request headers, Key values, or raw
Provider responses.

## Tests

M1 requires:

- repository tests for create/read/update/delete and restart recovery;
- optimistic version conflict tests;
- JSON round-trip and malicious/invalid import tests;
- secret scanning across SQLite, JSON, logs, checkpoints, and errors;
- fake-Provider tests for every error category;
- one explicit DeepSeek online test using an environment Key;
- LangGraph checkpoint restart test;
- Streamlit smoke and critical-flow browser tests.

## Acceptance

M1 passes when:

1. a project created in the UI is available after application restart;
2. project JSON exports and imports without semantic loss;
3. imported and persisted data contain no API Key;
4. DeepSeek connection testing succeeds with a valid runtime Key;
5. failure categories are clear and do not leak secrets;
6. LangGraph resumes the same project from its SQLite checkpoint;
7. all automated tests pass and the user confirms the local UI flow is
   understandable.
