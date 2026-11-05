#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Cyb3rF0xX
"""Thin launcher so `python3 server.py` works from a clone without installing.
The real server lives in the recordward package. If you installed via
pip, use `recordward serve` instead.

Flags: --port N, --no-open  (defaults come from your settings).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recordward import server  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="recordward local web app")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()
    server.run(port=args.port, open_browser=not args.no_open)
