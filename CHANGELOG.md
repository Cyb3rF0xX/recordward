# Changelog

All notable changes to RecordWard are recorded here. Versions follow
[semantic versioning](https://semver.org): MAJOR.MINOR.PATCH.

## [1.0.0]

First public release under the **GNU AGPLv3**.

Features
- CLI + local web app to track and request your own background-check /
  consumer-report records (US / FCRA).
- **Native launcher window** (`recordward app`): self-contained desktop window
  (via pywebview) with a first-run setup wizard and Launch / Preferences / Quit;
  falls back to a tkinter dialog, then a terminal menu.
- The dashboard renders **inside the native window** (no browser tab); the
  local server is hosted in-process on a private localhost port.
- **Reminders:** opt-in scheduled checks via a systemd user timer (Linux, no
  sudo): `recordward reminders set weekly|monthly|off`, `recordward notify`.
- **Idle auto-shutdown** so the server never lingers.
- Responsive dashboard that flows with window size, with a clear active-filter
  highlight.
- Per-OS data directories, settings, and data-reset (`recordward reset …`).
- Hardened localhost server: localhost-only bind, Host-header validation,
  strict Content-Security-Policy, request-size caps, input bounds. (`'unsafe-
  eval'` is permitted only when embedded in the native window, required by the
  webview bridge.)
- Test suite + CI on Linux/macOS/Windows across Python 3.9 and 3.12.
- Optional install extra `recordward[app]` (pywebview) for the native window;
  the CLI and `recordward serve` remain zero-dependency.

License
- Licensed under **AGPLv3-or-later**. Copyright (C) 2026 Cyb3rF0xX.
- The copyright holder may offer the software under separate commercial terms
  and may reassign the copyright (e.g. to a legal entity) in future.
