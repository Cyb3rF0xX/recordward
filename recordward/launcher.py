# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Cyb3rF0xX
"""Native launcher + first-run wizard for RecordWard (ADR-008).

Runs OUTSIDE the browser sandbox, so it can install/remove the systemd reminder
timer and manage app lifecycle. Renders the SAME visual language as the web
dashboard inside a pywebview window for a polished, on-brand experience.

Graceful degradation:
  1. pywebview present  -> native HTML window (preferred)
  2. else tkinter       -> simple native dialog
  3. else               -> terminal menu

Public entry point: run().
"""

from __future__ import annotations

import subprocess
import sys
import threading

from . import core
from . import reminders as rem
from . import settings as _settings


# --------------------------------------------------------------------------
# Actions shared by every front-end (GUI or terminal)
# --------------------------------------------------------------------------
def launch_app() -> None:
    """Start the web app in a detached process and open the browser.

    Used only as a fallback when the embedded native window isn't available.
    """
    import shutil

    exe = shutil.which("recordward")
    cmd = [exe, "serve"] if exe else [sys.executable, "-m", "recordward", "serve"]
    # Detach so closing the launcher doesn't kill the server; the server has
    # its own idle auto-shutdown so it won't linger forever.
    subprocess.Popen(cmd, start_new_session=True)


def _start_server_for_window() -> str | None:
    """Start the hardened local server on a free port, in-process, for the
    native window to display. Returns the URL, or None on failure.

    Same server + security as `recordward serve`, just hosted inside the app
    process so the dashboard renders in the pywebview window (no browser tab).
    The server also auto-stops when idle, so it won't linger.
    """
    try:
        import socket
        from http.server import ThreadingHTTPServer

        from . import server as srv

        # Mark the server as embedded so its CSP permits the webview bridge.
        srv.EMBEDDED = True

        # Find a free localhost port.
        s = socket.socket()
        s.bind((srv.HOST, 0))
        port = s.getsockname()[1]
        s.close()

        httpd = ThreadingHTTPServer((srv.HOST, port), srv.Handler)
        srv._touch()
        threading.Thread(
            target=srv._idle_watchdog, args=(httpd, 15), daemon=True
        ).start()
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return f"http://{srv.HOST}:{port}/"
    except Exception:
        return None


def set_reminders(cadence: str) -> dict:
    """Persist the reminder preference and apply the OS timer. Returns status."""
    _settings.set_value("reminders", cadence)
    try:
        rem.apply(cadence)
    except (RuntimeError, ValueError):
        pass
    _settings.set_value("setup_complete", True)
    return reminder_status()


def reminder_status() -> dict:
    s = _settings.load()
    st = rem.status()
    return {
        "preference": s["reminders"],
        "supported": st["supported"],
        "installed": st["installed"],
        "active": st["active"],
        "setup_complete": s["setup_complete"],
    }


def mark_setup_complete() -> None:
    _settings.set_value("setup_complete", True)


# --------------------------------------------------------------------------
# Front-end selection
# --------------------------------------------------------------------------
def run() -> None:
    core.bootstrap()
    first_run = not _settings.load()["setup_complete"]
    try:
        import webview  # noqa: F401

        _run_webview(first_run)
        return
    except ImportError:
        pass
    try:
        import tkinter  # noqa: F401

        _run_tk(first_run)
        return
    except ImportError:
        pass
    _run_terminal(first_run)


# --------------------------------------------------------------------------
# pywebview front-end (preferred, polished)
# --------------------------------------------------------------------------
def _run_webview(first_run: bool) -> None:
    import webview

    class Api:
        def get_status(self):
            return reminder_status()

        def set_reminders(self, cadence):
            return set_reminders(cadence)

        def skip_setup(self):
            mark_setup_complete()
            return reminder_status()

        def launch(self):
            # Open the dashboard INSIDE this native window (no browser tab).
            url = _start_server_for_window()
            if url:
                # Point the existing launcher window at the dashboard URL.
                for w in list(webview.windows):
                    try:
                        w.load_url(url)
                        break
                    except Exception:
                        pass
                return {"ok": True, "url": url}
            # Fallback: couldn't start the embedded server, use the browser.
            launch_app()
            threading.Timer(1.2, lambda: _close_all()).start()
            return {"ok": True, "browser": True}

        def quit(self):
            _close_all()
            return {"ok": True}

    def _close_all():
        for w in list(webview.windows):
            try:
                w.destroy()
            except Exception:
                pass

    api = Api()
    html = _launcher_html(first_run)
    webview.create_window(
        "RecordWard",
        html=html,
        js_api=api,
        width=480,
        height=580,
        min_size=(380, 480),
        resizable=True,      # flows with window size; dashboard is responsive
    )
    webview.start()


# --------------------------------------------------------------------------
# tkinter fallback (functional, not as pretty)
# --------------------------------------------------------------------------
def _run_tk(first_run: bool) -> None:
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title("RecordWard")
    root.geometry("380x320")

    tk.Label(root, text="RecordWard", font=("", 18, "bold")).pack(pady=(18, 2))
    tk.Label(root, text="Guard your own file.", fg="#555").pack()

    st = reminder_status()

    if first_run and st["supported"]:
        tk.Label(root, text="\nSet up reminders:", font=("", 11)).pack()
        var = tk.StringVar(value="off")
        for label, val in [("No reminders", "off"),
                           ("Weekly", "weekly"), ("Monthly", "monthly")]:
            tk.Radiobutton(root, text=label, variable=var, value=val).pack(anchor="w", padx=80)

        def save_and_continue():
            set_reminders(var.get())
            _build_main(root, tk)

        tk.Button(root, text="Save and continue", command=save_and_continue).pack(pady=12)
    else:
        _build_main(root, tk)

    root.mainloop()


def _build_main(root, tk) -> None:
    for w in root.winfo_children():
        w.destroy()
    tk.Label(root, text="RecordWard", font=("", 18, "bold")).pack(pady=(18, 2))
    tk.Label(root, text="Guard your own file.", fg="#555").pack(pady=(0, 10))

    st = reminder_status()
    rem_txt = f"Reminders: {st['preference']}"
    if not st["supported"]:
        rem_txt += " (scheduling not supported here)"
    tk.Label(root, text=rem_txt, fg="#555").pack()

    def do_launch():
        launch_app()
        root.after(1200, root.destroy)

    tk.Button(root, text="Launch app", width=20, command=do_launch).pack(pady=(14, 4))

    def open_prefs():
        from tkinter import simpledialog
        choice = simpledialog.askstring(
            "Reminders",
            "Reminders — type: off / weekly / monthly",
            initialvalue=st["preference"],
        )
        if choice:
            set_reminders(choice.strip().lower())
            _build_main(root, tk)

    tk.Button(root, text="Preferences", width=20, command=open_prefs).pack(pady=4)
    tk.Button(root, text="Quit", width=20, command=root.destroy).pack(pady=4)


# --------------------------------------------------------------------------
# Terminal fallback (last resort)
# --------------------------------------------------------------------------
def _run_terminal(first_run: bool) -> None:
    if first_run:
        core.cmd_init(assume_yes=False)
    while True:
        st = reminder_status()
        print("\nRecordWard")
        print(f"  reminders: {st['preference']}"
              + ("" if st["supported"] else "  (scheduling not supported here)"))
        print("  1) Launch app")
        print("  2) Preferences (reminders)")
        print("  3) Quit")
        try:
            choice = input("Choose [1]: ").strip() or "1"
        except EOFError:
            choice = "3"
        if choice == "1":
            launch_app()
            print("Launched. (The app auto-stops when idle.)")
            return
        elif choice == "2":
            cad = input("Reminders off/weekly/monthly: ").strip().lower()
            if cad in ("off", "weekly", "monthly"):
                set_reminders(cad)
                print(f"Set to {cad}.")
        else:
            return


# --------------------------------------------------------------------------
# Launcher HTML (on-brand, matches the dashboard design tokens)
# --------------------------------------------------------------------------
def _launcher_html(first_run: bool) -> str:
    st = reminder_status()
    wizard_display = "block" if (first_run and st["supported"]) else "none"
    main_display = "none" if (first_run and st["supported"]) else "block"
    rem_note = "" if st["supported"] else (
        '<p class="muted">Automatic reminders need Linux + systemd; not '
        "available here. The app still shows what's due when you open it.</p>"
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<style>
  :root {{ --bg:#0f1115; --panel:#171a21; --panel2:#1e222b; --text:#e6e8ec;
    --muted:#9aa3b2; --line:#2a2f3a; --accent:#5aa9ff; --ok:#4ade80; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); text-align:center;
    font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
    padding:28px 22px; }}
  h1 {{ margin:0; font-size:26px; letter-spacing:.5px; }}
  .tag {{ color:var(--muted); font-size:13px; margin:2px 0 20px; }}
  .card {{ background:var(--panel); border:1px solid var(--line);
    border-radius:14px; padding:20px; margin:0 auto; max-width:360px; }}
  h2 {{ font-size:15px; margin:0 0 12px; }}
  .btn {{ display:block; width:100%; text-align:center; text-decoration:none;
    background:var(--accent); color:#06101f; font-weight:700; border:none;
    padding:12px; border-radius:10px; cursor:pointer; font-size:15px;
    margin:10px 0; }}
  .btn:hover {{ filter:brightness(1.08); }}
  .btn.ghost {{ background:var(--panel2); color:var(--text);
    border:1px solid var(--line); }}
  .opts label {{ display:block; text-align:left; background:var(--panel2);
    border:1px solid var(--line); border-radius:8px; padding:10px 12px;
    margin:8px 0; cursor:pointer; }}
  .opts input {{ margin-right:10px; }}
  .muted {{ color:var(--muted); font-size:12px; }}
  .status {{ color:var(--muted); font-size:13px; margin:4px 0 14px; }}
  .status b {{ color:var(--ok); }}
</style></head><body>
  <h1>RecordWard</h1>
  <div class="tag">Guard your own file.</div>

  <div class="card" id="wizard" style="display:{wizard_display}">
    <h2>Welcome — set up reminders</h2>
    <p class="muted">Get a desktop notification when records are due.</p>
    <div class="opts">
      <label><input type="radio" name="cad" value="off" checked> No reminders</label>
      <label><input type="radio" name="cad" value="weekly"> Weekly check</label>
      <label><input type="radio" name="cad" value="monthly"> Monthly check</label>
    </div>
    <button class="btn" onclick="saveSetup()">Save and continue</button>
    {rem_note}
  </div>

  <div class="card" id="main" style="display:{main_display}">
    <h2>Ready</h2>
    <div class="status" id="rem-status"></div>
    <button class="btn" onclick="launch()">Launch app</button>
    <button class="btn ghost" onclick="togglePrefs()">Preferences</button>
    <button class="btn ghost" onclick="api().quit()">Quit</button>
    <div id="prefs" style="display:none; margin-top:12px;">
      <div class="opts">
        <label><input type="radio" name="pcad" value="off"> No reminders</label>
        <label><input type="radio" name="pcad" value="weekly"> Weekly</label>
        <label><input type="radio" name="pcad" value="monthly"> Monthly</label>
      </div>
      <button class="btn" onclick="savePrefs()">Save reminders</button>
      <p class="muted">To enable later from a terminal:
        <code>recordward reminders set weekly</code></p>
    </div>
  </div>

<script>
  function api() {{ return window.pywebview.api; }}
  async function refresh() {{
    const s = await api().get_status();
    const el = document.getElementById('rem-status');
    if (el) el.innerHTML = s.supported
      ? ('Reminders: <b>' + s.preference + '</b>'
         + (s.active ? ' (active)' : s.preference!=='off' ? ' (saved)' : ''))
      : 'Reminders: not available on this system';
    const p = document.querySelector('input[name=pcad][value="'+s.preference+'"]');
    if (p) p.checked = true;
  }}
  async function saveSetup() {{
    const v = document.querySelector('input[name=cad]:checked').value;
    await api().set_reminders(v);
    document.getElementById('wizard').style.display='none';
    document.getElementById('main').style.display='block';
    refresh();
  }}
  function togglePrefs() {{
    const p = document.getElementById('prefs');
    p.style.display = p.style.display==='none' ? 'block' : 'none';
  }}
  async function savePrefs() {{
    const v = document.querySelector('input[name=pcad]:checked').value;
    await api().set_reminders(v);
    refresh();
  }}
  async function launch() {{ await api().launch(); }}
  window.addEventListener('pywebviewready', refresh);
  setTimeout(refresh, 300);
</script>
</body></html>"""
