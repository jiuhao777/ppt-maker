from pathlib import Path
from types import SimpleNamespace

import pytest

from pptmaker.powerpoint.preflight import preflight_issues


def test_preflight_detects_internet_zone_identifier(tmp_path: Path):
    deck = tmp_path / "downloaded.pptx"
    deck.write_bytes(b"pptx")
    zone = Path(f"{deck}:Zone.Identifier")
    try:
        zone.write_text("[ZoneTransfer]\nZoneId=3\n", encoding="utf-8")
    except OSError:
        pytest.skip("filesystem does not support alternate data streams")

    assert "protected_view_risk" in preflight_issues(deck, process_iter=lambda: [])


def test_preflight_detects_exclusive_file_lock(tmp_path: Path):
    import win32con
    import win32file

    deck = tmp_path / "locked.pptx"
    deck.write_bytes(b"pptx")
    handle = win32file.CreateFile(
        str(deck),
        win32con.GENERIC_READ,
        0,
        None,
        win32con.OPEN_EXISTING,
        win32con.FILE_ATTRIBUTE_NORMAL,
        None,
    )
    try:
        assert "file_locked" in preflight_issues(deck, process_iter=lambda: [])
    finally:
        handle.Close()


def test_preflight_detects_existing_powerpoint(tmp_path: Path):
    deck = tmp_path / "input.pptx"
    deck.write_bytes(b"pptx")
    processes = lambda: [SimpleNamespace(info={"name": "POWERPNT.EXE", "pid": 42})]

    issues = preflight_issues(deck, process_iter=processes)

    assert "existing_powerpoint_instance" in issues


def test_preflight_accepts_clean_closed_file(tmp_path: Path):
    deck = tmp_path / "input.pptx"
    deck.write_bytes(b"pptx")

    assert preflight_issues(deck, process_iter=lambda: []) == []
