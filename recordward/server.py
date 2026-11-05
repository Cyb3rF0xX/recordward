#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Cyb3rF0xX
"""server.py - a tiny, hardened LOCAL web app for recordward.

Turns the static dashboard into an interactive one: Mark-done and Snooze
buttons work right in the browser, no terminal needed. It reuses all the
logic in recordward.py, so behavior is identical to the CLI.

Cross-platform: uses only Python's standard library (http.server), so there's
nothing to pip-install and it runs the same on Windows, macOS, and Linux.

Security model (local single-user tool):
  * Binds to 127.0.0.1 only - not reachable from other devices.
  * Rejects requests unless the client socket is a loopback peer (defense in
    depth against anything bound more broadly).
  * Validates the Host header against an allowlist - blocks DNS-rebinding,
    where a malicious web page resolves a hostname to 127.0.0.1 to reach this
    server from your browser.
  * Serves a strict Content-Security-Policy with a per-response nonce, plus
    X-Content-Type-Options / X-Frame-Options / Referrer-Policy.
  * Caps request body size (anti-DoS) and bounds all inputs.
  * State-changing routes are POST + JSON content-type only.

Run:
    python3 server.py              # starts on http://127.0.0.1:8765 and opens it
    python3 server.py --port 9000  # pick a port
    python3 server.py --no-open    # don't auto-open the browser

Stop with Ctrl+C.
"""

from __future__ import annotations

import ipaddress
import json
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import core as bg
from . import settings as _settings

import time

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_BODY_BYTES = 64 * 1024  # 64 KiB is plenty for a name + short note

# Last time any request was served; drives idle auto-shutdown (ADR-008).
_last_activity = time.monotonic()

# Set True by the native launcher when the dashboard is hosted inside the
# pywebview window (see CSP note in Handler._send). False for browser `serve`.
EMBEDDED = False


def _touch() -> None:
    global _last_activity
    _last_activity = time.monotonic()


def _current_statuses() -> list[dict]:
    sources = bg.load_sources(bg.SCHEDULE)
    log = bg.load_log()
    return [bg.status_for(s, log) for s in sources]


def _resolve(name: str) -> str | None:
    """Exact source-name match only (the UI always sends the full name)."""
    sources = bg.load_sources(bg.SCHEDULE)
    names = [s["name"] for s in sources]
    return name if name in names else None


class Handler(BaseHTTPRequestHandler):
    # The port we're bound to - set on the server instance in main().
    server_version = "recordward"
    sys_version = ""  # don't leak the Python version in the Server header

    def log_message(self, fmt, *args):
        # Quiet during tests (RECORDWARD_QUIET set) to keep output readable.
        if os.environ.get("RECORDWARD_QUIET"):
            return
        print(f"  {self.address_string()} - {fmt % args}")

    # ---- security gate --------------------------------------------------
    def _client_is_loopback(self) -> bool:
        try:
            return ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            return False

    def _host_allowed(self) -> bool:
        """Only accept Host headers we expect for local use.

        Blocks DNS-rebinding: a page at evil.com can't point a hostname at
        127.0.0.1 and talk to us, because its Host header won't match.
        """
        host = self.headers.get("Host", "")
        port = self.server.server_address[1]
        allowed = {
            f"127.0.0.1:{port}",
            f"localhost:{port}",
            f"[::1]:{port}",
        }
        # Some browsers omit the port for default ports; accept bare host too.
        allowed |= {"127.0.0.1", "localhost", "[::1]"}
        return host in allowed

    def _guard(self) -> bool:
        _touch()  # any (even rejected) request counts as activity
        if not self._client_is_loopback():
            self._send(403, b"forbidden", "text/plain; charset=utf-8")
            return False
        if not self._host_allowed():
            self._send(
                421,
                b"misdirected request (bad Host)",
                "text/plain; charset=utf-8",
            )
            return False
        return True

    # ---- helpers --------------------------------------------------------
    def _send(
        self, code: int, body: bytes, ctype: str, nonce: str = ""
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        # Strict CSP: no external anything; inline script only via our nonce.
        # When hosted inside the native pywebview window (EMBEDDED=True), the
        # webview injects an eval-based Python<->JS bridge, so 'unsafe-eval' is
        # required there. This is safe in that context: it's our own HTML in a
        # dedicated app window, not a general browser with untrusted content.
        # The browser `serve` path keeps the strict, eval-free policy.
        script_src = f"'nonce-{nonce}'" if nonce else "'none'"
        if EMBEDDED and nonce:
            script_src += " 'unsafe-eval'"
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; "
            "style-src 'unsafe-inline'; "
            f"script-src {script_src}; "
            "connect-src 'self'; "
            "form-action 'none'; "
            "base-uri 'none'; "
            "frame-ancestors 'none'",
        )
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_html(self, html: str, code: int = 200, nonce: str = "") -> None:
        self._send(code, html.encode("utf-8"), "text/html; charset=utf-8", nonce)

    def _send_json(self, obj: dict, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

    def _read_json(self) -> dict | None:
        """Read a JSON body with hard limits. Returns None on any problem."""
        # Require a declared, sane Content-Length.
        raw_len = self.headers.get("Content-Length")
        if raw_len is None:
            return None
        try:
            length = int(raw_len)
        except ValueError:
            return None
        if length <= 0 or length > MAX_BODY_BYTES:
            return None
        # Require JSON content-type for state-changing requests.
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip()
        if ctype != "application/json":
            return None
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None

    # ---- routes ---------------------------------------------------------
    def do_GET(self):
        if not self._guard():
            return
        if self.path in ("/", "/index.html"):
            nonce = secrets.token_urlsafe(16)
            page = bg.render_page(
                _current_statuses(),
                interactive=True,
                script_nonce=nonce,
                snooze_days=_settings.load()["default_snooze_days"],
            )
            self._send_html(page, nonce=nonce)
        elif self.path == "/api/status":
            data = [
                {
                    "name": s["source"]["name"],
                    "due": s["due"],
                    "next_due": s["next_due"].isoformat(),
                    "snoozed": s.get("snoozed", False),
                }
                for s in _current_statuses()
            ]
            self._send_json({"statuses": data})
        elif self.path == "/api/settings":
            self._send_json({"settings": _settings.load()})
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if not self._guard():
            return
        valid_routes = ("/api/done", "/api/snooze", "/api/settings", "/api/reset")
        if self.path not in valid_routes:
            self._send_json({"ok": False, "error": "not found"}, 404)
            return

        body = self._read_json()
        if body is None:
            self._send_json({"ok": False, "error": "bad request"}, 400)
            return

        # --- settings & reset don't need a source name --------------------
        if self.path == "/api/settings":
            changed = {}
            for k, v in body.items():
                if k in _settings.DEFAULT_SETTINGS:
                    try:
                        _settings.set_value(k, v)
                        changed[k] = _settings.load()[k]
                    except (KeyError, ValueError, TypeError):
                        pass
            self._send_json({"ok": True, "settings": _settings.load()})
            return

        if self.path == "/api/reset":
            what = str(body.get("what", ""))
            fns = {
                "history": bg.reset_history,
                "snoozes": bg.reset_snoozes,
                "schedule": bg.reset_schedule,
                "all": bg.reset_all,
            }
            if what not in fns:
                self._send_json({"ok": False, "error": "bad scope"}, 400)
                return
            fns[what]()
            bg.regenerate_dashboard(bg.load_sources(bg.SCHEDULE))
            self._send_json({"ok": True})
            return

        # --- done / snooze need a valid source name -----------------------
        name = _resolve(str(body.get("name", "")))
        if not name:
            self._send_json({"ok": False, "error": "unknown source"}, 400)
            return

        sources = bg.load_sources(bg.SCHEDULE)
        if self.path == "/api/done":
            note = body.get("note")
            note = str(note) if note is not None else None
            bg.record_done(name, note)  # recordward sanitizes/bounds the note
            bg.regenerate_dashboard(sources)
            self._send_json({"ok": True})
        else:  # /api/snooze
            try:
                days = int(body.get("days", 30))
            except (TypeError, ValueError):
                days = 30
            days = max(1, min(days, 3650))
            until = bg.record_snooze(name, days)
            bg.regenerate_dashboard(sources)
            self._send_json({"ok": True, "until": until.isoformat()})


def _idle_watchdog(server: ThreadingHTTPServer, idle_minutes: int) -> None:
    """Shut the server down after `idle_minutes` with no requests (ADR-008)."""
    if idle_minutes <= 0:
        return  # 0 = never auto-shutdown
    idle_seconds = idle_minutes * 60
    while True:
        time.sleep(min(30, idle_seconds))
        if time.monotonic() - _last_activity >= idle_seconds:
            print(f"\nIdle for {idle_minutes} min — shutting down.")
            threading.Thread(target=server.shutdown, daemon=True).start()
            return


def run(
    port: int | None = None,
    open_browser: bool | None = None,
    idle_minutes: int | None = None,
) -> None:
    """Start the local web app. Falls back to user settings for defaults."""
    bg.bootstrap()
    s = _settings.load()
    port = port if port is not None else s["port"]
    if open_browser is None:
        open_browser = s["open_browser"]
    if idle_minutes is None:
        idle_minutes = s.get("idle_shutdown_minutes", 15)

    if not (1 <= port <= 65535):
        sys.exit(f"error: port must be 1-65535, got {port}")

    try:
        server = ThreadingHTTPServer((HOST, port), Handler)
    except OSError as e:
        sys.exit(
            f"error: can't bind {HOST}:{port} ({e}). "
            "Is it already in use? Try a different --port."
        )

    url = f"http://{HOST}:{port}/"
    print(f"recordward web app running at {url}")
    print("Bound to localhost only - not reachable from other devices.")
    if idle_minutes > 0:
        print(f"Will auto-stop after {idle_minutes} min idle. Ctrl+C to stop now.")
    else:
        print("Press Ctrl+C to stop.")

    _touch()  # reset the idle clock at startup
    threading.Thread(
        target=_idle_watchdog, args=(server, idle_minutes), daemon=True
    ).start()

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()
