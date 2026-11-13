"""Local Windows notification handler.

Dispatches balloon/toast notifications via scripts/notify.ps1 using PowerShell,
supporting both native Windows execution and WSL environments.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def trigger_windows_notification(title: str, message: str, logger=None) -> bool:
    """Send a local Windows notification if running on Windows or within WSL."""
    project_root = Path(__file__).resolve().parent.parent
    notify_script = project_root / "scripts" / "notify.ps1"

    if not notify_script.exists():
        if logger:
            logger.warning(f"Notification script not found at {notify_script}")
        return False

    ps_exe = None
    script_arg = None

    if sys.platform == "win32":
        ps_exe = shutil.which("powershell.exe") or "powershell.exe"
        script_arg = str(notify_script)
    else:
        # Running under Linux / WSL
        # Find Windows powershell.exe executable
        candidate_paths = [
            shutil.which("powershell.exe"),
            "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            "/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe",
        ]
        for candidate in candidate_paths:
            if candidate and os.path.exists(candidate):
                ps_exe = candidate
                break

        # Resolve Windows path to notify.ps1
        try:
            res = subprocess.run(["wslpath", "-w", str(notify_script)], capture_output=True, text=True, check=False)
            if res.returncode == 0 and res.stdout.strip():
                script_arg = res.stdout.strip().replace("\\", "/")
        except Exception:
            pass

        if not script_arg:
            # Fallback to standard drive mount mapping
            script_arg = "C:/Users/ihars/Desktop/Workspace/jobSearch/scripts/notify.ps1"

    if not ps_exe:
        if logger:
            logger.warning("powershell.exe not found. Notification skipped.")
        return False

    cmd = [
        ps_exe,
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        script_arg,
        "-Title",
        title,
        "-Message",
        message,
    ]

    try:
        subprocess.run(
            cmd,
            check=False,
            timeout=12,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if logger:
            logger.info(f"Local Windows notification triggered: [{title}] {message}")
        return True
    except Exception as e:
        if logger:
            logger.warning(f"Failed to trigger Windows notification: {e}")
        return False

