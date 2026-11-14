# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Cyb3rF0xX
"""Entry point for the bundled (PyInstaller) build.

Double-clicking the bundle passes no arguments, so open the native launcher
window. Any arguments are passed through to the normal CLI.
"""
import sys

from recordward import applog
from recordward.core import main

if __name__ == "__main__":
    # No console in the bundled app: record errors in recordward-app.log.
    applog.enable()
    args = sys.argv[1:]
    main(args if args else ["app"])
