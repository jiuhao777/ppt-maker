import re
import tempfile
from pathlib import Path
from tempfile import TemporaryDirectory

from pptmaker.m0.parser_probe import (
    ParsedDocument,
    parse_markdown,
    parse_pptx,
    parse_with_markitdown,
)
from pptmaker.m2.models import MaterialChunk, MaterialIngestResult
from pptmaker.security.uploads import (
    ArchiveLimits,
    UnsafeArchive,
    inspect_office_package,
)


MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SUPPORTED = {".md", ".docx", ".pdf", ".pptx"}
UNRECOGNIZED_WARNING = "图片或扫描型 PDF 暂未识别"


def temporary_root() -> Path:
    return Path(tempfile.gettempdir())


def _meaningful_text(text: str) -> str:
    without_images = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    return without_images.strip()


def _chunks_from_parsed(
    project_id: str,
    source_name: str,
    parsed: ParsedDocument,
) -> list[MaterialChunk]:
    paragraphs = [item.strip() for item in parsed.text.splitlines() if item.strip()]
    chunks = []
    for index, paragraph in enumerate(paragraphs):
        location = (
            parsed.locations[index]
            if index < len(parsed.locations)
            else "document"
        )
        for offset in range(0, len(paragraph), 100_000):
            chunks.append(
                MaterialChunk(
                    project_id=project_id,
                    source_name=source_name,
                    location=location,
                    text=paragraph[offset : offset + 100_000],
                )
            )
    return chunks


def ingest_material(
    project_id: str,
    filename: str,
    content: bytes,
) -> MaterialIngestResult:
    source_name = Path(filename).name
    suffix = Path(source_name).suffix.lower()
    if len(content) > MAX_UPLOAD_BYTES:
        return MaterialIngestResult(
            status="rejected",
            warning="文件超过 50 MiB 限制",
        )
    if suffix not in SUPPORTED:
        return MaterialIngestResult(
            status="unrecognized",
            warning=UNRECOGNIZED_WARNING,
        )
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        return MaterialIngestResult(
            status="rejected",
            warning="文件未通过安全检查",
        )

    try:
        with TemporaryDirectory(
            prefix="pptmaker-m2-",
            dir=temporary_root(),
        ) as folder:
            path = Path(folder) / source_name
            path.write_bytes(content)
            if suffix in {".docx", ".pptx"}:
                inspect_office_package(path, ArchiveLimits())
            if suffix == ".md":
                parsed = parse_markdown(content.decode("utf-8"))
            elif suffix == ".pptx":
                parsed = parse_pptx(path)
            else:
                parsed = parse_with_markitdown(path)
            if not _meaningful_text(parsed.text):
                return MaterialIngestResult(
                    status="unrecognized",
                    warning=UNRECOGNIZED_WARNING,
                )
            return MaterialIngestResult(
                status="parsed",
                chunks=_chunks_from_parsed(project_id, source_name, parsed),
            )
    except UnsafeArchive:
        return MaterialIngestResult(
            status="rejected",
            warning="文件未通过安全检查",
        )
    except Exception:
        return MaterialIngestResult(
            status="failed",
            warning="文件解析失败",
        )
