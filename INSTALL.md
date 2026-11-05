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
  search your app menu for "recordward".
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

## Standalone binary (advanced)

To produce a single executable that doesn't require Python installed, use
[PyInstaller](https://pyinstaller.org) on each target OS:

```bash
pip install pyinstaller
pyinstaller --onefile --name recordward \
  --collect-submodules recordward \
  -c "import sys; from recordward.core import main; main(sys.argv[1:])"
```

Build on the OS you're targeting (PyInstaller does not cross-compile). The
resulting binary lands in `dist/`.
