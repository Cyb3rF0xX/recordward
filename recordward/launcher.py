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

import logging

from . import core
from . import reminders as rem
from . import settings as _settings

core_log = logging.getLogger("recordward.launcher")


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
def _clamp_to_screen(webview, width: int, height: int) -> tuple[int, int]:
    """Limit a size to 90% of the primary screen when it can be read."""
    try:
        scr = webview.screens[0]
        width = min(width, int(scr.width * 0.9))
        height = min(height, int(scr.height * 0.9))
    except Exception:
        pass
    return width, height


_NAVIGATE_DELAY_S = 0.3


def _grown_height(webview, current: int, extra_px) -> int:
    """New window height: current + hidden content, capped to the screen."""
    try:
        extra = max(0, int(extra_px))
    except (TypeError, ValueError):
        extra = 0
    _, max_h = _clamp_to_screen(webview, 0, 100000)
    return min(int(current) + extra, max_h)


def _open_dashboard(webview, url: str) -> None:
    """Grow the compact launch window and point it at the dashboard."""
    for w in list(webview.windows):
        try:
            # The launch screen is compact; the running app needs room for
            # 2+ columns, so grow the window now.
            aw, ah = _default_window_size(webview)
            _resize_window(webview, w, aw, ah)
            w.load_url(url)
            break
        except Exception:
            core_log.exception("could not open the dashboard in the window")


def _window_icon(platform: str | None = None) -> str:
    """Icon file for the native window, in the format each backend accepts.

    pywebview's Windows backend loads it with System.Drawing.Icon, which only
    accepts .ico (a PNG crashes the app with ArgumentException). GTK/Qt/Cocoa
    take PNG.
    """
    platform = platform or sys.platform
    name = "icon.ico" if platform.startswith("win") else "icon-256.png"
    return str(core.asset_path(name))


def _launcher_window_size(webview) -> tuple[int, int]:
    """Compact size for the launch screen (it only holds a small card)."""
    w, h = _clamp_to_screen(webview, 480, 500)
    return max(w, 380), max(h, 480)


def _default_window_size(webview) -> tuple[int, int]:
    """Size for the running app: wide enough for 2+ dashboard columns.

    About 1100x780, clamped to the primary screen so small displays still get
    a window that fits.
    """
    w, h = _clamp_to_screen(webview, 1100, 780)
    return max(w, 700), max(h, 520)


def _resize_window(webview, win, width: int, height: int, center: bool = True) -> None:
    """Resize (and best-effort re-center) a window. Never raises."""
    try:
        win.resize(int(width), int(height))
    except Exception:
        return
    if not center:
        return
    try:
        scr = webview.screens[0]
        win.move(max(0, (scr.width - width) // 2), max(0, (scr.height - height) // 2))
    except Exception:
        pass  # e.g. Wayland forbids client-side moves; the resize still applied
def _run_webview(first_run: bool) -> None:
    import webview

    state = {"max": False, "full": False}
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
                # Navigate a moment AFTER returning. pywebview delivers this
                # method's return value to the page's JS callback; navigating
                # first destroys that callback and pywebview logs a
                # JavascriptException ("_returnValuesCallbacks ... is not a
                # function"), seen on Windows and Linux.
                threading.Timer(
                    _NAVIGATE_DELAY_S, _open_dashboard, args=(webview, url)
                ).start()
                return {"ok": True, "url": url}
            # Fallback: couldn't start the embedded server, use the browser.
            launch_app()
            threading.Timer(1.2, lambda: _close_all()).start()
            return {"ok": True, "browser": True}

        def quit(self):
            _close_all()
            return {"ok": True}
        def fit_height(self, extra_px):
            """Grow (never shrink) the launch window by the content height the
            page reports as hidden, e.g. when Preferences or the setup wizard
            opens. The page measures it, so this works whatever the OS counts
            in the window height (Windows includes the title bar and borders).
            """
            if not webview.windows or state["max"] or state["full"]:
                return {"ok": False}
            try:
                w = webview.windows[0]
                want = _grown_height(webview, w.height, extra_px)
                if want > w.height:
                    _resize_window(webview, w, w.width, want, center=False)
                return {"ok": True}
            except Exception:
                return {"ok": False}
        def window_control(self, action):
            """Minimize / maximize-restore / fullscreen, on any OS."""
            if not webview.windows:
                return {"ok": False}
            w = webview.windows[0]
            try:
                if action == "minimize":
                    w.minimize()
                elif action == "fullscreen":
                    w.toggle_fullscreen()
                    state["full"] = not state["full"]
                elif action == "maximize":
                    if state["full"]:
                        w.toggle_fullscreen()
                        state["full"] = False
                    elif state["max"]:
                        w.restore()
                        state["max"] = False
                    else:
                        w.maximize()
                        state["max"] = True
                elif action == "restore":
                    if state["full"]:
                        w.toggle_fullscreen()
                        state["full"] = False
                    w.restore()
                    state["max"] = False
                else:
                    return {"ok": False}
            except Exception:
                return {"ok": False}
            return {"ok": True, **state}

    def _close_all():
        for w in list(webview.windows):
            try:
                w.destroy()
            except Exception:
                pass

    api = Api()
    html = _launcher_html(first_run)
    width, height = _launcher_window_size(webview)
    webview.create_window(
        "RecordWard",
        html=html,
        js_api=api,
        width=width,
        height=height,
        min_size=(380, 480),
        resizable=True,      # flows with window size; dashboard is responsive
    )
    icon = _window_icon()
    # Wayland/KDE/GNOME pick the title-bar and taskbar icon by matching the
    # window app-id to an installed recordward.desktop (Icon=recordward), so
    # name the GTK program accordingly. Harmless/no-op elsewhere.
    try:
        from gi.repository import GLib
        GLib.set_prgname("recordward")
        GLib.set_application_name("RecordWard")
    except Exception:
        pass
    try:
        # `icon` sets the title-bar/taskbar icon on GTK and Qt backends;
        # Windows/macOS take it from the packaged app or are ignored.
        webview.start(icon=icon)
    except TypeError:
        webview.start()  # older pywebview without the icon argument


# --------------------------------------------------------------------------
# tkinter fallback (functional, not as pretty)
# --------------------------------------------------------------------------
def _run_tk(first_run: bool) -> None:
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title("RecordWard")
    try:
        root._rw_icon = tk.PhotoImage(file=str(core.asset_path("icon-64.png")))
        root.iconphoto(True, root._rw_icon)
    except Exception:
        pass  # icon is cosmetic; never block the launcher on it
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
    # Only offer reminder choices where they can actually be scheduled.
    if st["supported"]:
        prefs_body = """<div class="opts">
        <label><input type="radio" name="pcad" value="off"> No reminders</label>
        <label><input type="radio" name="pcad" value="weekly"> Weekly</label>
        <label><input type="radio" name="pcad" value="monthly"> Monthly</label>
      </div>
      <button class="btn" onclick="savePrefs()">Save reminders</button>
      <p class="muted">To enable later from a terminal:
        <code>recordward reminders set weekly</code></p>"""
    else:
        prefs_body = (
            '<p class="muted" id="no-reminders">Automatic reminders aren\'t '
            "available on this system yet (they currently need Linux with "
            "systemd). Open RecordWard any time to see what's due.</p>"
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<style>
  :root {{ --bg:#0f1115; --panel:#171a21; --panel2:#1e222b; --text:#e6e8ec;
    --muted:#9aa3b2; --line:#2a2f3a; --accent:#5aa9ff; --ok:#4ade80; }}
  * {{ box-sizing:border-box; }}
  body {{ overflow-wrap:anywhere; margin:0; background:var(--bg); color:var(--text); text-align:center;
    font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
    padding:28px 22px; }}
  h1 {{ margin:0; font-size:26px; letter-spacing:.5px; }}
  .mark {{ margin:0 0 6px; line-height:0; }}
  .tag {{ color:var(--muted); font-size:13px; margin:2px 0 20px; }}
  .card {{ background:var(--panel); border:1px solid var(--line);
    border-radius:14px; padding:20px; margin:0 auto 14px; max-width:360px; width:100%; min-width:0; }}
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
  code {{ overflow-wrap:anywhere; }}
  .status {{ color:var(--muted); font-size:13px; margin:4px 0 14px; }}
  .status b {{ color:var(--ok); }}
</style></head><body>
  <div class="mark">{core.logo_svg(72)}</div>
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
      {prefs_body}
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
    fitWindow();
  }}
  // Ask the host to grow the compact launch window if content doesn't fit
  // (Preferences panel, first-run wizard). Never shrinks.
  function fitWindow() {{
    try {{
      if (api() && api().fit_height) {{
        const extra = document.documentElement.scrollHeight - window.innerHeight;
        if (extra > 0) api().fit_height(extra + 8);
      }}
    }} catch (e) {{}}
  }}
  function togglePrefs() {{
    const p = document.getElementById('prefs');
    p.style.display = p.style.display==='none' ? 'block' : 'none';
    fitWindow();
  }}
  async function savePrefs() {{
    const v = document.querySelector('input[name=pcad]:checked').value;
    await api().set_reminders(v);
    refresh();
  }}
  async function launch() {{ await api().launch(); }}
  window.addEventListener('pywebviewready', refresh);
  setTimeout(refresh, 300);
  setTimeout(fitWindow, 400);
</script>
</body></html>"""
