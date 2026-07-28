# PPT Maker

Local-first AI presentation agent for Windows 11 and Microsoft PowerPoint.

## Current workflow

1. Enter a topic or upload source material.
2. Confirm requirements and approve the overview outline.
3. Run optional Bocha web research after outline approval.
4. Generate a detailed Deck Blueprint.
5. Review safely downloaded image candidates.
6. Approve the Blueprint before generating PPTX.

PPT generation compiles the approved Blueprint deterministically. It does not
make another LLM request. Generated text, tables and charts remain editable;
approved images are cropped without stretching; source blocks and speaker notes
are retained. Completed files are restored from SQLite by Blueprint version
after a browser refresh.

API keys exist only in the current Streamlit session and are lost on refresh.
They are not written to SQLite, project exports, files or logs.

## Environment boundaries

| Capability | Requirement | Degradation |
|---|---|---|
| Core project, outline and Blueprint | Python 3.10–3.12 | Available without PowerPoint |
| LLM generation | A compatible provider API key | Manual project data remains available |
| Current factual research | Optional Bocha API key | `AUTO` warns and continues; `ALWAYS` blocks |
| Open image candidates | Internet access | Use no-image layouts or user-provided images |
| PPTX generation | Python libraries | Produces editable `.pptx` |
| PowerPoint render verification | Windows 11 + Microsoft PowerPoint | Skip preview/render verification |
| Local visual model | Supported NVIDIA GPU | Geometry and rule checks only |

WPS, macOS/Linux PowerPoint automation and cloud deployment are not supported
in the first version.

## Run locally

```bat
conda activate AI
streamlit run src/pptmaker/ui/app.py
```

The server binds to `127.0.0.1`; an external URL is intentionally unavailable.
See [manual acceptance](docs/manual-acceptance.md) for the complete workflow,
PowerPoint checks and online-provider checks.

## Automated checks

```bat
conda activate AI
set PYTHONIOENCODING=utf-8
python -m pytest -q
python scripts/check_p4_product_acceptance_gate.py
```

## Image discovery

Image search prioritizes Bocha-discovered Chinese webpages, Bing China and
domestic search adapters, then uses Openverse and Wikimedia as optional
fallbacks. License and author metadata do not filter personal-use candidates.
Remote images are downloaded only after SSRF, redirect, MIME, byte-size,
decoded-format and pixel-dimension checks.
