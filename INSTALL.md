# Installing RecordWard

Works on Linux, macOS, and Windows. Needs **Python 3.9+**. Zero runtime
dependencies (standard library only).

## Recommended: pipx (isolated, clean uninstall)

[pipx](https://pipx.pypa.io) installs the `recordward` command on your PATH in its
own environment.

```bash
pipx install git+https://github.com/Cyb3rF0xX/recordward
```

Then:

```bash
recordward serve      # start the web app (opens your browser)
recordward due        # what's due now (terminal)
recordward --help     # all commands
```

Update / remove:

```bash
pipx upgrade recordward
pipx uninstall recordward
```

## Alternative: pip

```bash
pip install --user git+https://github.com/Cyb3rF0xX/recordward
# or, from a clone:
pip install .
```

## No install: just clone and run

```bash
git clone https://github.com/Cyb3rF0xX/recordward
cd recordward
python3 server.py      # web app
python3 recordward.py due # CLI
```

## Where your data lives

Your schedule, logs, and settings are stored in the per-OS app directory, not
next to the code, so they survive reinstalls:

| OS | Location |
|----|----------|
| Linux | `~/.config/recordward/` (config), `~/.local/share/recordward/` (data) |
| macOS | `~/Library/Application Support/recordward/` |
| Windows | `%APPDATA%\recordward\` |

See the exact paths anytime with `recordward where`. Override the location with the
`RECORDWARD_HOME` environment variable (handy for a fully portable setup).

## Clickable launchers (optional)

- **Linux:** `cp recordward.desktop ~/.local/share/applications/` then
  search your app menu for "recordward". For the app icon, also copy
  `recordward/assets/icon.svg` to
  `~/.local/share/icons/hicolor/scalable/apps/recordward.svg`.
- **macOS:** double-click `launchers/recordward.command` (you may need to
  right-click → Open the first time).
- **Windows:** double-click `launchers/recordward.pyw` (runs without a console
  window via the `.pyw` association).

## Settings and cleanup

```bash
recordward config                     # show settings
recordward config default_snooze_days 60
recordward reset snoozes              # clear snoozes
recordward reset history              # clear request history
recordward reset schedule            # restore the default schedule
recordward reset all                 # erase ALL local data
```

The same settings and cleanup actions are available in the web app's
**Settings** panel.

## Ready-made app download (preview, no Python needed)

Each release on the [Releases page](https://github.com/Cyb3rF0xX/recordward/releases)
has a download for Windows (`.zip`), macOS (`.zip`) and Linux (`.tar.gz`).
Unzip it and run `RecordWard` (Windows: `RecordWard.exe`).

These builds are **unsigned** for now:
- **Windows:** SmartScreen may warn "Windows protected your PC". Click
  **More info**, then **Run anyway**.
- **macOS:** the app is blocked the first time. Right-click it, choose
  **Open**, then confirm (or allow it under System Settings > Privacy &
  Security).
- **Linux:** needs WebKitGTK installed (most GNOME/KDE desktops have it).

To build these yourself, see [packaging/README.md](packaging/README.md).
Build on the OS you're targeting (PyInstaller does not cross-compile).
