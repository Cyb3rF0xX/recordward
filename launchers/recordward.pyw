#!/usr/bin/env pythonw
"""Windows double-clickable launcher (no console window).

Save this on your Desktop or pin it. Double-clicking runs the web app using
pythonw (the .pyw association), so no black console window appears.

It tries, in order:
  1. the installed `recordward serve` command (if you pip/pipx-installed), then
  2. a server.py sitting next to the repo, then
  3. the importable package.
"""

import os
import subprocess
import sys


def main() -> None:
    # 1) installed console command
    exe = "recordward.exe" if os.name == "nt" else "recordward"
    try:
        subprocess.Popen([exe, "serve"])
        return
    except (FileNotFoundError, OSError):
        pass

    # 2/3) run from the package if it's importable
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)  # launchers/ -> repo root
    if repo not in sys.path:
        sys.path.insert(0, repo)
    try:
        from recordward import server
        server.run()
    except Exception as e:  # noqa: BLE001 - show something useful on failure
        import tkinter.messagebox as mb

        mb.showerror(
            "recordward",
            "Could not start.\n\nInstall it with:\n"
            "pipx install git+https://github.com/Cyb3rF0xX/recordward\n\n"
            f"Details: {e}",
        )


if __name__ == "__main__":
    main()
