# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Cyb3rF0xX
"""Manage the reminder schedule (systemd user timer) from inside the app.

This runs OUTSIDE the browser sandbox (called by the native wrapper / CLI), so
it is allowed to install and remove a per-user systemd timer that periodically
checks whether any records are due and fires a desktop notification.

Linux/systemd only. On other platforms (or when systemctl is unavailable) the
functions degrade gracefully and report that scheduling isn't supported here;
the rest of the app still works, and the web UI reflects the real status.

No sudo required: everything is in the per-user systemd scope
(~/.config/systemd/user).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

UNIT_SERVICE = "recordward-reminder.service"
UNIT_TIMER = "recordward-reminder.timer"

# OnCalendar expressions per cadence.
_CALENDAR = {
    "weekly": "Mon *-*-* 10:00:00",
    "monthly": "*-*-01 10:00:00",
}


def _user_unit_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "systemd" / "user"


def supported() -> bool:
    """True only on Linux with a usable `systemctl --user`."""
    if sys.platform != "linux":
        return False
    if shutil.which("systemctl") is None:
        return False
    try:
        # `systemctl --user` fails without a user bus (e.g. some containers).
        r = subprocess.run(
            ["systemctl", "--user", "is-system-running"],
            capture_output=True,
            timeout=5,
        )
        # Any answer (even "degraded"/non-zero) means the user bus responded.
        return r.returncode == 0 or r.stdout.strip() != b""
    except (OSError, subprocess.TimeoutExpired):
        return False


def _notify_command() -> str:
    """Command the service runs: check due items and notify if any.

    Uses the installed `recordward` console script. ExecStart must be an
    absolute path for systemd, so resolve it; fall back to `python -m`.
    """
    exe = shutil.which("recordward")
    if exe:
        return f"{exe} notify"
    return f"{sys.executable} -m recordward notify"


def status() -> dict:
    """Report whether the timer is installed and active."""
    if not supported():
        return {"supported": False, "installed": False, "active": False}
    installed = (_user_unit_dir() / UNIT_TIMER).exists()
    active = False
    if installed:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", UNIT_TIMER],
            capture_output=True,
            text=True,
        )
        active = r.stdout.strip() == "active"
    return {"supported": True, "installed": installed, "active": active}


def install(cadence: str) -> dict:
    """Install/refresh the reminder timer for 'weekly' or 'monthly'.

    Returns a status dict. Raises RuntimeError with a readable message if the
    platform doesn't support it.
    """
    if cadence not in _CALENDAR:
        raise ValueError(f"cadence must be weekly/monthly, got {cadence!r}")
    if not supported():
        raise RuntimeError("systemd user timers aren't available on this system.")

    unit_dir = _user_unit_dir()
    unit_dir.mkdir(parents=True, exist_ok=True)

    (unit_dir / UNIT_SERVICE).write_text(
        "[Unit]\n"
        "Description=RecordWard - check for due records and notify\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={_notify_command()}\n",
        encoding="utf-8",
    )
    (unit_dir / UNIT_TIMER).write_text(
        "[Unit]\n"
        f"Description=RecordWard reminder ({cadence})\n\n"
        "[Timer]\n"
        f"OnCalendar={_CALENDAR[cadence]}\n"
        "Persistent=true\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n",
        encoding="utf-8",
    )

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(
        ["systemctl", "--user", "enable", "--now", UNIT_TIMER], check=False
    )
    return status()


def uninstall() -> dict:
    """Disable and remove the reminder timer. Idempotent."""
    if not supported():
        return {"supported": False, "installed": False, "active": False}
    subprocess.run(
        ["systemctl", "--user", "disable", "--now", UNIT_TIMER], check=False
    )
    unit_dir = _user_unit_dir()
    for name in (UNIT_TIMER, UNIT_SERVICE):
        p = unit_dir / name
        if p.exists():
            p.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    return {"supported": True, "installed": False, "active": False}


def apply(cadence: str) -> dict:
    """Make the system match the desired cadence ('off'/'weekly'/'monthly')."""
    if cadence == "off":
        return uninstall()
    return install(cadence)
