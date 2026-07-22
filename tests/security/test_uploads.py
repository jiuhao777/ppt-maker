import stat
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from pptmaker.security.uploads import (
    ArchiveLimits,
    UnsafeArchive,
    inspect_office_package,
    inspect_zip,
)


def _archive(tmp_path: Path, name: str, members: dict[str, bytes | str]) -> Path:
    path = tmp_path / name
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for member_name, content in members.items():
            archive.writestr(member_name, content)
    return path


@pytest.mark.parametrize("member", ["../escape.txt", "C:/escape.txt", "//server/share.txt", "\\\\server\\share.txt"])
def test_rejects_path_traversal_and_windows_roots(tmp_path: Path, member: str):
    archive = _archive(tmp_path, "bad.zip", {member: "x"})
    with pytest.raises(UnsafeArchive, match="path traversal"):
        inspect_zip(archive, ArchiveLimits())


def test_rejects_symbolic_link(tmp_path: Path):
    archive = tmp_path / "symlink.zip"
    link = ZipInfo("link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with ZipFile(archive, "w") as handle:
        handle.writestr(link, "target")
    with pytest.raises(UnsafeArchive, match="symbolic links"):
        inspect_zip(archive, ArchiveLimits())


def test_rejects_encrypted_member_flag(monkeypatch, tmp_path: Path):
    member = SimpleNamespace(
        filename="secret.txt",
        external_attr=0,
        flag_bits=1,
        file_size=1,
        compress_size=1,
    )

    class FakeArchive:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def infolist(self):
            return [member]

    monkeypatch.setattr("pptmaker.security.uploads.ZipFile", lambda _path: FakeArchive())
    with pytest.raises(UnsafeArchive, match="encrypted"):
        inspect_zip(tmp_path / "encrypted.zip", ArchiveLimits())


@pytest.mark.parametrize("member", ["nested.zip", "nested.7z", "nested.rar", "nested.gz"])
def test_rejects_nested_archives(tmp_path: Path, member: str):
    archive = _archive(tmp_path, "nested.zip", {member: b"PK\x03\x04"})
    with pytest.raises(UnsafeArchive, match="nested archives"):
        inspect_zip(archive, ArchiveLimits())


def test_rejects_single_member_and_total_size_limits(tmp_path: Path):
    archive = _archive(tmp_path, "large.zip", {"large.txt": "x" * 2048})
    with pytest.raises(UnsafeArchive, match="single member"):
        inspect_zip(archive, ArchiveLimits(max_member_bytes=1024))
    with pytest.raises(UnsafeArchive, match="uncompressed size"):
        inspect_zip(
            archive,
            ArchiveLimits(max_member_bytes=4096, max_uncompressed_bytes=1024),
        )


def test_rejects_extreme_compression_ratio(tmp_path: Path):
    archive = _archive(tmp_path, "bomb.zip", {"zeros.txt": "0" * 100_000})
    with pytest.raises(UnsafeArchive, match="compression ratio"):
        inspect_zip(archive, ArchiveLimits(max_ratio=2, max_member_bytes=200_000))


@pytest.mark.parametrize("member", ["ppt/vbaProject.bin", "ppt/embeddings/oleObject1.bin", "ppt/activeX/activeX1.bin", "ppt/externalLinks/link.xml"])
def test_rejects_active_or_embedded_office_content(tmp_path: Path, member: str):
    package = _archive(
        tmp_path,
        "unsafe.pptx",
        {"[Content_Types].xml": "<Types/>", "ppt/presentation.xml": "<p/>", member: "x"},
    )
    with pytest.raises(UnsafeArchive, match="macro, OLE, ActiveX, embedding, or external link"):
        inspect_office_package(package, ArchiveLimits())


def test_rejects_docx_renamed_as_pptx(tmp_path: Path):
    package = _archive(
        tmp_path,
        "renamed.pptx",
        {"[Content_Types].xml": "<Types/>", "word/document.xml": "<w/>",},
    )
    with pytest.raises(UnsafeArchive, match="extension does not match"):
        inspect_office_package(package, ArchiveLimits())


@pytest.mark.parametrize(
    ("name", "root_member"),
    [("safe.pptx", "ppt/presentation.xml"), ("safe.docx", "word/document.xml")],
)
def test_accepts_minimal_safe_office_packages(tmp_path: Path, name: str, root_member: str):
    package = _archive(
        tmp_path,
        name,
        {"[Content_Types].xml": "<Types/>", root_member: "<root/>",},
    )
    inspection = inspect_office_package(package, ArchiveLimits())
    assert inspection.members == 2
