# M0.1 Closure Design

## Purpose

Close the gaps found in the second M0 review without expanding into M1 product
features. M0.1 makes the existing technical evidence trustworthy, closes the
real-network SSRF gap, makes the PowerPoint Worker retry-safe, publishes
reviewable evidence, and leaves only the user's visual acceptance as a manual
gate.

## Scope

M0.1 changes four bounded subsystems:

1. Probe evidence identity and deterministic gate validation.
2. DNS-pinned HTTP(S) fetching.
3. PowerPoint Worker idempotency, atomic output publication, and cleanup.
4. Sanitized evidence publication and execution-plan status.

It does not add a search Provider, visual model, frontend, Agent workflow, or
new document formats.

## Evidence and Gate

`ProbeResult` gains:

- `schema_version`;
- UTC `generated_at`;
- `source_fingerprint`;
- environment metadata containing Python, platform, and relevant dependency
  versions.

The source fingerprint is a SHA-256 over the normalized bytes of the Probe
implementation, its directly exercised production modules, `pyproject.toml`,
and the environment lock. It is independent of Git commit timing, so evidence
can be generated and committed without immediately becoming stale.

The M0 gate defines a policy per mandatory Probe. Each policy validates:

- result name and schema;
- `status == pass`;
- current source fingerprint;
- required metric names and thresholds;
- evidence paths for Probes that produce files;
- environment compatibility.

The gate rejects legacy or manually edited JSON that lacks identity metadata.
The DeepSeek evidence records the model and base URL host, never the API key.

## DNS-Pinned Fetching

URL validation returns a `ValidatedTarget` rather than discarding the DNS
answer. It contains the original scheme, hostname, port, and the complete set
of validated public IP addresses.

The production fetcher connects to one validated IP directly. For HTTPS it
performs TLS with `server_hostname` set to the original hostname, preserving
certificate hostname verification and SNI. The HTTP `Host` header also uses the
original hostname. The operating-system resolver is never called between
validation and connection.

Every redirect starts a new validation and pinning cycle. Redirects, timeouts,
status handling, MIME allowlists, declared and streamed size limits retain the
existing behavior. Tests include a resolver that changes to a private address
after validation and assert that the connection still receives only the
previously validated public IP.

## PowerPoint Worker Protocol

The single-process lock remains the serialization boundary. Each request gets:

- an idempotency record keyed by `idempotency_key`;
- an input SHA-256 and normalized request fingerprint;
- a task-specific temporary output directory;
- a final output directory published only after slide-count and path
  validation.

If the same idempotency key and request fingerprint already completed, the
client returns the validated recorded response without launching PowerPoint.
If the key is reused with different input or parameters, the request fails
closed. An incomplete record is recoverable: stale temporary output is
quarantined and the task can retry.

The Worker exports into a sibling temporary directory, validates numeric slide
ordering and expected slide count, then atomically renames it to the final
directory. The parent client attempts precise owned-PID cleanup after every
failed response, invalid response, nonzero Worker exit, or timeout. Cleanup
still requires PID, creation time, process name, and run ID to match.

Fault-injection tests cover `Presentation.Close` and `Application.Quit`
failures, invalid Worker output, idempotent replay, conflicting key reuse, and
no orphaned owned process.

## Published Evidence

Runtime artifacts remain ignored. A deterministic exporter creates
`docs/evidence/m0/` containing:

- sanitized mandatory Probe JSON;
- full-suite test summary;
- SHA-256 for the baseline PPTX and rendered slides;
- environment summary;
- a manifest linking every snapshot to its source fingerprint.

Absolute local paths, usernames, API keys, raw model responses, and temporary
directories are removed. The snapshot is committed so a GitHub reviewer can
inspect the evidence, while the gate continues to use freshly generated local
artifacts.

## Documentation and Acceptance

The M0 execution plan checkboxes are synchronized with reality. All automated
steps become complete; human visual review remains unchecked until the user
opens the baseline PPTX and rendered PNGs.

The gate report distinguishes:

- automated M0.1 PASS;
- non-blocking exploration items;
- pending human visual acceptance.

M0 is formally closed only after the user confirms the visual result and that
decision is recorded in the report.

## Testing

Each subsystem is developed test-first and committed independently:

1. Evidence identity and stale-evidence rejection.
2. DNS-pinned HTTP and HTTPS connector behavior.
3. PowerPoint idempotency, atomic publication, and failure cleanup.
4. Evidence snapshot and documentation synchronization.

The final verification runs the complete suite with the repository-local
pytest temporary directory, regenerates all six mandatory Probes, runs the
gate, and checks that the Git worktree contains only intentional evidence and
documentation changes.

