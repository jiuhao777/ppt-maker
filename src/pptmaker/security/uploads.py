from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile


class UnsafeArchive(ValueError):
    pass


@dataclass(frozen=True)
class ArchiveLimits:
    max_members: int = 5000
    max_uncompressed_bytes: int = 200 * 1024 * 1024
    max_member_bytes: int = 50 * 1024 * 1024
    max_ratio: float = 200.0
    max_nested_archives: int = 0


@dataclass(frozen=True)
class ArchiveInspection:
    members: int
    compressed_bytes: int
    uncompressed_bytes: int


def inspect_zip(path: Path, limits: ArchiveLimits) -> ArchiveInspection:
    try:
        with ZipFile(path) as archive:
            members = archive.infolist()
    except (BadZipFile, OSError) as exc:
        raise UnsafeArchive("invalid ZIP container") from exc

    if len(members) > limits.max_members:
        raise UnsafeArchive("member count exceeds limit")
    for member in members:
        normalized = member.filename.replace("\\", "/")
        candidate = PurePosixPath(normalized)
        unix_mode = member.external_attr >> 16
        is_symlink = (unix_mode & 0o170000) == 0o120000
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or ":" in member.filename
            or normalized.startswith("//")
        ):
            raise UnsafeArchive("path traversal detected")
        if is_symlink:
            raise UnsafeArchive("symbolic links are forbidden")
        if member.flag_bits & 0x1:
            raise UnsafeArchive("encrypted members are forbidden")
        if member.file_size > limits.max_member_bytes:
            raise UnsafeArchive("single member exceeds limit")
        if (
            candidate.suffix.lower() in {".zip", ".7z", ".rar", ".gz"}
            and limits.max_nested_archives == 0
        ):
            raise UnsafeArchive("nested archives are forbidden")
        if candidate.suffix.lower() in {".exe", ".dll", ".js", ".vbs", ".ole"}:
            raise UnsafeArchive("active or embedded content is forbidden")

    compressed = sum(member.compress_size for member in members)
    uncompressed = sum(member.file_size for member in members)
    if uncompressed > limits.max_uncompressed_bytes:
        raise UnsafeArchive("uncompressed size exceeds limit")
    ratio = uncompressed / max(compressed, 1)
    if ratio > limits.max_ratio:
        raise UnsafeArchive("compression ratio exceeds limit")
    return ArchiveInspection(len(members), compressed, uncompressed)


def inspect_office_package(path: Path, limits: ArchiveLimits) -> ArchiveInspection:
    extension = path.suffix.lower()
    if extension not in {".docx", ".pptx", ".xlsx"}:
        raise UnsafeArchive("only non-macro OOXML extensions are allowed")
    try:
        with path.open("rb") as stream:
            signature = stream.read(4)
    except OSError as exc:
        raise UnsafeArchive("Office package cannot be read") from exc
    if signature != b"PK\x03\x04":
        raise UnsafeArchive("extension does not match ZIP-based OOXML type")

    inspection = inspect_zip(path, limits)
    with ZipFile(path) as archive:
        names = {item.filename.replace("\\", "/").lower() for item in archive.infolist()}
    if "[content_types].xml" not in names:
        raise UnsafeArchive("Office package is missing content type metadata")
    expected_root = {".docx": "word/", ".pptx": "ppt/", ".xlsx": "xl/"}[extension]
    if not any(name.startswith(expected_root) for name in names):
        raise UnsafeArchive("extension does not match Office package contents")
    forbidden = (
        "vbaproject.bin",
        "/embeddings/",
        "oleobject",
        "activex",
        "externallinks/",
    )
    if any(any(marker in name for marker in forbidden) for name in names):
        raise UnsafeArchive(
            "macro, OLE, ActiveX, embedding, or external link is forbidden"
        )
    return inspection
