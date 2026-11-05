#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Cyb3rF0xX
"""Thin launcher so `python3 recordward.py ...` works from a clone without
installing. The real code lives in the recordward package next to this
file. If you installed via pip, use the `recordward` command instead.
"""

import sys
from pathlib import Path

# Make the package importable when run directly from the repo.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from recordward.core import main  # noqa: E402

if __name__ == "__main__":
    main(sys.argv[1:])
