# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Cyb3rF0xX
"""User settings: a small JSON file in the config dir.

Keys (see defaults.DEFAULT_SETTINGS):
  port                int    default web-app port
  open_browser        bool   auto-open the browser when the server starts
  default_snooze_days int    snooze length used by the web app's Snooze button
  notify              bool   whether notify.sh pops a desktop notification
"""

from __future__ import annotations

import json
from typing import Any

from . import paths
from .defaults import DEFAULT_SETTINGS

# Per-key validation/coercion so a hand-edited file can't break the app.
def _coerce_reminders(v):
    v = str(v).lower()
    return v if v in ("off", "weekly", "monthly") else "off"


_COERCE = {
    "port": lambda v: max(1, min(int(v), 65535)),
    "open_browser": lambda v: bool(v),
    "default_snooze_days": lambda v: max(1, min(int(v), 3650)),
    "notify": lambda v: bool(v),
    "setup_complete": lambda v: bool(v),
    "reminders": _coerce_reminders,
    "idle_shutdown_minutes": lambda v: max(0, min(int(v), 1440)),
}


def load() -> dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)
    f = paths.settings_file()
    if f.exists():
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            raw = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if k in _COERCE:
                    try:
                        settings[k] = _COERCE[k](v)
                    except (ValueError, TypeError):
                        pass  # keep default on bad value
    return settings


def save(settings: dict[str, Any]) -> None:
    paths.ensure_dirs()
    clean = {}
    for k, default in DEFAULT_SETTINGS.items():
        v = settings.get(k, default)
        try:
            clean[k] = _COERCE[k](v)
        except (ValueError, TypeError):
            clean[k] = default
    paths.settings_file().write_text(
        json.dumps(clean, indent=2) + "\n", encoding="utf-8"
    )


def set_value(key: str, value: Any) -> dict[str, Any]:
    if key not in DEFAULT_SETTINGS:
        raise KeyError(key)
    s = load()
    s[key] = value
    save(s)
    return s
