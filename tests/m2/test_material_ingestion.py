import pytest
from PIL import Image

from pptmaker.m0.parser_probe import generate_parser_fixtures
from pptmaker.m2 import materials
from pptmaker.m2.materials import ingest_material


@pytest.fixture
def fixture_files(tmp_path):
    root = tmp_path / "fixtures"
    generate_parser_fixtures(root)
    return root


@pytest.mark.parametrize(
    "name",
    ["sample.md", "sample.docx", "sample.pdf", "sample.pptx"],
)
def test_supported_material_produces_chunks(name, fixture_files):
    result = ingest_material("p1", name, (fixture_files / name).read_bytes())

    assert result.status == "parsed"
    assert result.chunks
    assert all(chunk.source_name == name for chunk in result.chunks)


def test_image_and_scanned_pdf_are_explicitly_unrecognized(tmp_path):
    image = tmp_path / "scan.png"
    Image.new("RGB", (100, 100), "white").save(image)
    scan = tmp_path / "scan.pdf"
    Image.open(image).save(scan, "PDF")

    image_result = ingest_material("p1", image.name, image.read_bytes())
    scan_result = ingest_material("p1", scan.name, scan.read_bytes())

    assert image_result.status == "unrecognized"
    assert scan_result.status == "unrecognized"
    assert image_result.warning == "图片或扫描型 PDF 暂未识别"
    assert scan_result.warning == "图片或扫描型 PDF 暂未识别"


def test_task_temp_directory_is_removed_after_parser_failure(
    monkeypatch,
    tmp_path,
):
    temporary_root = tmp_path / "temporary"
    temporary_root.mkdir()
    monkeypatch.setattr(materials, "temporary_root", lambda: temporary_root)
    monkeypatch.setattr(
        materials,
        "parse_with_markitdown",
        lambda path: (_ for _ in ()).throw(ValueError("private")),
    )

    result = ingest_material("p1", "broken.pdf", b"%PDF-1.7")

    assert result.status == "failed"
    assert result.warning == "文件解析失败"
    assert list(temporary_root.iterdir()) == []


def test_unsafe_office_package_is_rejected():
    result = ingest_material("p1", "fake.docx", b"not an office package")

    assert result.status == "rejected"
    assert result.warning == "文件未通过安全检查"
