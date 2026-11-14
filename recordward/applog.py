# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Cyb3rF0xX
"""Error log for the app window, mainly for the bundled (no-console) builds.

The downloadable Windows/macOS/Linux apps have no console, so without this a
crash or a webview error would vanish silently. When enabled, warnings,
errors and unhandled exceptions are written to ``recordward-app.log`` in the
data directory (see ``recordward where``), capped at about 1 MB in total.

Privacy: only program messages and tracebacks are logged. Tracebacks show
code locations, not variable values, so request notes and personal data are
not written here.
"""
from __future__ import annotations

import logging
import logging.handlers
import platform
import sys
import threading
from pathlib import Path

from . import __version__, paths

MAX_BYTES = 512 * 1024  # per file; one backup is kept (~1 MB total)
BACKUPS = 1

log = logging.getLogger("recordward")

_handler: logging.Handler | None = None
_saved: dict = {}


class _StreamToLog:
    """File-like stand-in for a missing sys.stdout/sys.stderr (no console)."""

    def __init__(self, logger: logging.Logger, level: int) -> None:
        self._logger = logger
        self._level = level
        self._buf = ""

    def write(self, text: str) -> int:
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self._logger.log(self._level, line.rstrip())
        return len(text)

    def flush(self) -> None:
        if self._buf.strip():
            self._logger.log(self._level, self._buf.rstrip())
        self._buf = ""

    def isatty(self) -> bool:
        return False


def enable(path: Path | None = None) -> Path:
    """Start logging to the app log. Safe to call more than once."""
    global _handler
    path = Path(path) if path else paths.app_log_file()
    if _handler is not None:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    _saved.update(
        root_level=root.level,
        log_level=log.level,
        stdout_level=logging.getLogger("stdout").level,
        excepthook=sys.excepthook,
        threading_excepthook=threading.excepthook,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    root.addHandler(handler)
    root.setLevel(logging.WARNING)  # keep third-party chatter out
    log.setLevel(logging.INFO)      # our own startup line
    logging.getLogger("stdout").setLevel(logging.INFO)  # stray prints
    _handler = handler

    def _excepthook(exc_type, exc, tb):
        log.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
        _saved["excepthook"](exc_type, exc, tb)

    def _thread_excepthook(args):
        log.critical(
            "Unhandled exception in thread %s",
            getattr(args.thread, "name", "?"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        _saved["threading_excepthook"](args)

    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook
    # No console (windowed build): send stray prints/errors to the log too.
    if sys.stdout is None:
        sys.stdout = _StreamToLog(logging.getLogger("stdout"), logging.INFO)
    if sys.stderr is None:
        sys.stderr = _StreamToLog(logging.getLogger("stderr"), logging.WARNING)

    log.info(
        "RecordWard %s starting (%s %s, Python %s, bundled=%s)",
        __version__, platform.system(), platform.release(),
        platform.python_version(), bool(getattr(sys, "frozen", False)),
    )
    return path


def disable() -> None:
    """Stop logging and restore the previous hooks/streams (used by tests)."""
    global _handler
    if _handler is None:
        return
    root = logging.getLogger()
    root.removeHandler(_handler)
    _handler.close()
    _handler = None
    root.setLevel(_saved["root_level"])
    log.setLevel(_saved["log_level"])
    logging.getLogger("stdout").setLevel(_saved["stdout_level"])
    sys.excepthook = _saved["excepthook"]
    threading.excepthook = _saved["threading_excepthook"]
    sys.stdout = _saved["stdout"]
    sys.stderr = _saved["stderr"]
    _saved.clear()
