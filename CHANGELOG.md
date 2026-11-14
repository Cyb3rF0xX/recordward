# Changelog

All notable changes to RecordWard are recorded here. Versions follow
[semantic versioning](https://semver.org): MAJOR.MINOR.PATCH.

## [1.1.0] - 2026-11-14
Added
- **Larger app window:** the launch screen stays compact (about 480 px wide) and
  the window grows to about 1100x780 (clamped to the screen) when you press
  Launch app, so the dashboard opens with two or more columns. Opening
  Preferences or the first-run wizard grows the launch window only as far as
  its content needs.
- **Window controls** (minimize, maximize/restore, full screen, F11) on the
  dashboard inside the native window. Cross-platform; not shown on the launch
  screen or in a normal browser.
- **Free-request limits:** new optional `min_days` per source in
  `schedule.yaml`. Cards show "free limit: once per Nd" and warn when your
  reminder (`every_days`) is shorter than the provider allows.
- **Per-company guidance:** step-by-step request, review, dispute, freeze,
  fraud-alert and opt-out instructions, with official links.
- **App logo and icon:** a shield-and-file mark (single SVG source, plus a
  simplified small-size variant, PNGs 16-512 and a multi-size `.ico`) used
  for the window/title-bar icon (pywebview and tkinter), the dashboard
  favicon and header, the launcher, and the Linux desktop entries
  (`Icon=recordward`). Regenerate with `scripts/make-icons.sh`.
- **App error log:** the app window (and the downloadable apps, which have
  no console) writes warnings, errors and crashes to `recordward-app.log` in
  the data folder (`recordward where` shows the path; about 1 MB max; no
  personal data). "Erase everything" removes it.
- Tests for limits, guidance coverage, icons, app log, and version consistency.
- **Ready-made app downloads (preview):** Windows, macOS and Linux bundles
  that don't need Python, built by GitHub Actions and attached to each release.
  Unsigned for now (Windows SmartScreen and macOS warn on first run; Linux
  needs WebKitGTK). See INSTALL.md.

Changed
- Default intervals corrected to match free-request limits: LexisNexis
  90 -> 365 days; Checkr, Sterling, HireRight, First Advantage and Accurate
  180 -> 365 days. Credit bureaus stay at 30 days (free weekly access).
- Sterling, First Advantage and Accurate default links now point to their
  consumer pages (Sterling via its CFPB listing).
- Recipients-list guidance now states the 2-year (employment) and 1-year
  (other purposes) periods.
- The CSP now allows `img-src data:` (used only for the inline favicon).
- Existing `schedule.yaml` files are not modified. Use Settings > Reset
  schedule (this discards custom edits) to adopt the new defaults.

Fixed
- Preferences no longer offers reminder choices on systems that can't
  schedule them (Windows, macOS); it explains instead.
- The launch screen no longer shows a needless scrollbar on Windows.
- Launch app no longer logs a spurious JavaScript error: the window now
  switches to the dashboard just after the button's call returns.
- The Windows app no longer crashes on start: the window icon is now an
  `.ico` file there (Windows rejected the PNG).
- Step links are now readable on the dark theme (were default dark blue), and
  card titles wrap at spaces instead of breaking mid-word.
- Text, badges, buttons and borders no longer break out of cards, the settings
  panel or the launcher when the window is resized; the sticky header no longer
  covers content in short windows.

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
