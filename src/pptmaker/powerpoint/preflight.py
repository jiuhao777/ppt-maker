from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

import psutil
import pywintypes
import win32con
import win32file
import winreg


class ProcessLike(Protocol):
    info: dict


ProcessIterator = Callable[[], Iterable[ProcessLike]]


def _system_processes() -> Iterable[ProcessLike]:
    return psutil.process_iter(["name", "pid"])


def preflight_issues(
    path: Path,
    process_iter: ProcessIterator = _system_processes,
) -> list[str]:
    issues: list[str] = []
    if not path.is_file():
        issues.append("input_missing")
        return issues

    zone_path = Path(f"{path}:Zone.Identifier")
    try:
        zone = zone_path.read_text(encoding="utf-8", errors="ignore")
        if "ZoneId=3" in zone or "ZoneId=4" in zone:
            issues.append("protected_view_risk")
    except OSError:
        pass

    handle = None
    try:
        handle = win32file.CreateFile(
            str(path),
            win32con.GENERIC_READ,
            0,
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_ATTRIBUTE_NORMAL,
            None,
        )
    except (OSError, pywintypes.error):
        issues.append("file_locked")
    finally:
        if handle is not None:
            handle.Close()

    existing = [
        process.info.get("pid")
        for process in process_iter()
        if (process.info.get("name") or "").lower() == "powerpnt.exe"
    ]
    if existing:
        issues.append("existing_powerpoint_instance")
    return issues


def _registry_value(root, key_path: str, value_name: str):
    try:
        with winreg.OpenKey(root, key_path) as key:
            return winreg.QueryValueEx(key, value_name)[0]
    except OSError:
        return None


def office_environment() -> dict[str, str | int | bool | None]:
    click_to_run = r"SOFTWARE\Microsoft\Office\ClickToRun\Configuration"
    powerpoint_security = r"Software\Microsoft\Office\16.0\PowerPoint\Security"
    return {
        "office_version": _registry_value(
            winreg.HKEY_LOCAL_MACHINE, click_to_run, "VersionToReport"
        ),
        "office_bitness": _registry_value(
            winreg.HKEY_LOCAL_MACHINE, click_to_run, "Platform"
        ),
        "office_products": _registry_value(
            winreg.HKEY_LOCAL_MACHINE, click_to_run, "ProductReleaseIds"
        ),
        "macro_vba_warnings": _registry_value(
            winreg.HKEY_CURRENT_USER, powerpoint_security, "VBAWarnings"
        ),
    }
