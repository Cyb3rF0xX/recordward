# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Cyb3rF0xX
"""Enable `python -m recordward`."""

import sys

from .core import main

if __name__ == "__main__":
    main(sys.argv[1:])
