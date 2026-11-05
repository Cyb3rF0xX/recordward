# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Cyb3rF0xX
"""Per-OS data/config directory resolution for recordward.

Standard-library only (no `platformdirs` dependency). Picks the conventional
per-user location for each platform so the tool behaves like a real installed
app and user data never lives inside the installed package:

    Linux:    data   $XDG_DATA_HOME     or ~/.local/share/recordward
              config $XDG_CONFIG_HOME   or ~/.config/recordward
    macOS:    ~/Library/Application Support/recordward (data + config)
    Windows:  %APPDATA%\\recordward (data + config)

Override everything with RECORDWARD_HOME=/some/dir (useful for testing and for a
fully portable "keep it all in one folder" setup).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP = "recordward"


def _env(name: str) -> Path | None:
    val = os.environ.get(name)
    return Path(val).expanduser() if val else None


def data_dir() -> Path:
    override = _env("RECORDWARD_HOME")
    if override:
        return override
    if sys.platform == "win32":
        base = _env("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return base / APP
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP
    # Linux / other Unix
    base = _env("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return base / APP


def config_dir() -> Path:
    override = _env("RECORDWARD_HOME")
    if override:
        return override
    if sys.platform == "win32":
        base = _env("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return base / APP
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP
    base = _env("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return base / APP


def ensure_dirs() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    config_dir().mkdir(parents=True, exist_ok=True)


# Concrete file locations -------------------------------------------------
def schedule_file() -> Path:
    return config_dir() / "schedule.yaml"


def settings_file() -> Path:
    return config_dir() / "settings.json"


def log_file() -> Path:
    return data_dir() / "requests.log"


def history_file() -> Path:
    return data_dir() / "history.log"


def dashboard_file() -> Path:
    return data_dir() / "dashboard.html"
