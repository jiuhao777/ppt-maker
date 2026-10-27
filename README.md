# PPT Maker

> **归档说明：本项目已停止开发，是一个失败项目的完整过程记录。**
> 生成质量未达到可用标准，选题本身也被否定。代码可以运行，但不保证产出可用的演示文稿。
> 终止原因、最终状态、未入库的大文件（`models/` 共 12.26 GB 本地模型权重）及其重新下载方式，
> 全部记录在 **[docs/ARCHIVE.md](docs/ARCHIVE.md)**。逐日开发过程见 [`ppt-maker.txt`](ppt-maker.txt)。

Local-first AI presentation agent for Windows 11 and Microsoft PowerPoint.

## Current workflow

1. Enter a topic or upload source material.
2. Run Bocha research before the overview outline when freshness is required.
3. Confirm requirements and approve the overview outline.
4. Generate a detailed Deck Blueprint with executable page geometry.
5. Review image candidates independently for up to four planned slots per page.
6. Approve the Blueprint before generating PPTX.

PPT generation compiles the approved Blueprint deterministically. It does not
make another LLM request. Generated text, tables and charts remain editable;
approved images are cropped without stretching; source blocks and speaker notes
are retained. Completed files are restored from SQLite by Blueprint version
after a browser refresh.

Each detailed Blueprint page records its conclusion, content hierarchy, layout,
image purpose and placement, highlights, speaker notes and page-to-page bridge.
The normal editor uses readable descriptions; normalized coordinates are
available under advanced settings. Older Blueprint payloads are migrated when
loaded and saved as a new version. Manual edits made after export in PowerPoint
do not synchronize back into the Blueprint.

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
