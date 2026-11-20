"""Windows Startup and background lifecycle management."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def get_windows_startup_dir() -> Optional[Path]:
    """Return the Windows user Startup directory (shell:startup)."""
    if os.name != "nt":
        return None
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def get_vbs_script_path() -> Optional[Path]:
    startup_dir = get_windows_startup_dir()
    if startup_dir:
        return startup_dir / "mindnotes-watcher.vbs"
    return None


def enable_autostart() -> Path:
    """
    Register a silent background watcher that launches on Windows login.
    Uses a small VBScript runner with pythonw.exe to avoid any console popup.
    """
    if os.name != "nt":
        raise NotImplementedError("Autostart registration is currently only implemented for Windows.")

    startup_dir = get_windows_startup_dir()
    if not startup_dir or not startup_dir.exists():
        raise RuntimeError("Windows Startup directory could not be located.")

    vbs_path = startup_dir / "mindnotes-watcher.vbs"

    # Find pythonw.exe corresponding to current Python executable
    python_exe = Path(sys.executable)
    pythonw_exe = python_exe.parent / "pythonw.exe"
    runner = str(pythonw_exe) if pythonw_exe.exists() else str(python_exe)

    # VBScript to run pythonw in the background without a console window (window style 0)
    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        f'WshShell.Run """{runner}"" -m mindnotes.cli watch", 0, False\n'
    )

    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    return vbs_path


def disable_autostart() -> bool:
    """Remove silent background watcher from Windows Startup."""
    vbs_path = get_vbs_script_path()
    if vbs_path and vbs_path.exists():
        vbs_path.unlink()
        return True
    return False


def is_autostart_enabled() -> bool:
    """Check if Mindnotes background watcher is configured to run on login."""
    vbs_path = get_vbs_script_path()
    return vbs_path is not None and vbs_path.exists()
