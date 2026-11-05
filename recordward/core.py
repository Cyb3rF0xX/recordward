#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Cyb3rF0xX
"""recordward - a local scheduler/log for regularly requesting your own
background-check and consumer-report records (US / FCRA).

It does NOT log into any site or pull data for you - those sites require your
authentication and don't offer consumer APIs. What it does:

  * reads schedule.yaml (a list of sources + how often each is due),
  * compares against requests.log (what you've already requested, and when),
  * tells you what's due now,
  * optionally opens the relevant URLs in your browser,
  * lets you record ("mark done") a request so the clock resets.

Commands
--------
  recordward.py due            Show what's due now (default).
  recordward.py list           Show every source with its next-due date.
  recordward.py open           Show what's due and open those URLs in a browser.
  recordward.py done NAME      Record a request for NAME (uses today's date).
  recordward.py done NAME --note "got file, no new inquiries"
  recordward.py log            Print the request history.

Files (kept next to this script)
  schedule.yaml   you edit this
  requests.log    the tool appends to this; one JSON object per line

No third-party dependencies - standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import webbrowser
from pathlib import Path

from . import paths
from .defaults import DEFAULT_SCHEDULE_YAML

# User data/config now live in per-OS app dirs (see paths.py), not next to the
# code - so the tool works when pip-installed and data survives reinstalls.
SCHEDULE = paths.schedule_file()
LOG = paths.log_file()
HISTORY = paths.history_file()
DASHBOARD = paths.dashboard_file()

# Legacy location: older versions kept files next to the script. We migrate
# these into the app dir on first run so nobody loses history on upgrade.
_LEGACY_DIR = Path(__file__).resolve().parent.parent
_LEGACY = {
    "schedule.yaml": SCHEDULE,
    "requests.log": LOG,
    "history.log": HISTORY,
}


def bootstrap() -> None:
    """Make sure dirs exist, migrate legacy files, and seed a default schedule.

    Safe to call on every entry point; it does nothing once set up.
    """
    paths.ensure_dirs()

    # One-time migration from the old next-to-script layout.
    for fname, dest in _LEGACY.items():
        src = _LEGACY_DIR / fname
        if src.exists() and not dest.exists():
            try:
                dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                pass

    # Seed the schedule from the packaged default if the user has none.
    if not SCHEDULE.exists():
        SCHEDULE.write_text(DEFAULT_SCHEDULE_YAML, encoding="utf-8")


def today() -> dt.date:
    """Current date, read fresh each call.

    A function (not a module constant) so a long-running server - which may
    stay up across midnight - always computes 'due' against the real date.
    """
    return dt.date.today()


# --------------------------------------------------------------------------
# Per-source step-by-step instructions for the dashboard. Keyed by a
# substring of the source name so it keeps working if you lightly rename a
# source in schedule.yaml. First matching key wins; order matters.
# --------------------------------------------------------------------------
INSTRUCTIONS: list[tuple[str, list[str]]] = [
    (
        "AnnualCreditReport",
        [
            "Open the site and choose to request your report (you can do all "
            "three bureaus, but this card is for one — pull the matching one).",
            "Verify your identity (SSN, DOB, address; they may ask security "
            "questions).",
            "Open the report and go straight to the <b>Inquiries</b> section.",
            "Look under <b>soft / promotional / employment inquiries</b> for "
            "any name you don't recognize or any employer/screener.",
            "Save or screenshot the inquiries list so you can compare next time.",
            "Reports are free weekly, so pulling often is fine and never hurts "
            "your score.",
        ],
    ),
    (
        "LexisNexis",
        [
            "Open the consumer disclosure request page.",
            "Submit a <b>Full File Disclosure</b> request (free under FCRA).",
            "Verify your identity; the report usually arrives by mail/secure "
            "delivery, not instantly.",
            "When it arrives, review it for background/employment data and any "
            "recipients listed.",
            "Optional but recommended: place a <b>LexisNexis security freeze</b> "
            "while you're there.",
        ],
    ),
    (
        "CFPB",
        [
            "Open the CFPB list of consumer reporting companies.",
            "Scan the <b>Employment Screening</b> and specialty sections.",
            "Note any screener you recognize (e.g. one an employer used) that "
            "isn't already in your schedule.",
            "Add it as a new source in <code>schedule.yaml</code> so it gets "
            "tracked.",
        ],
    ),
    # Fallback for the employment screeners (Checkr, Sterling, HireRight,
    # First Advantage, Accurate). Matches any name — keep it LAST.
    (
        "",
        [
            "Open the vendor's consumer / candidate portal (link below).",
            "Request a <b>copy of your file disclosure</b> (free under FCRA).",
            "Also request the <b>list of recipients in the past 2 years</b> — "
            "FCRA entitles you to know who pulled a report on you for "
            "employment purposes.",
            "Verify your identity as prompted.",
            "When the file arrives, check it for accuracy and for any recipient "
            "you don't recognize.",
            "If anything is wrong, use their <b>dispute</b> process to correct "
            "it.",
        ],
    ),
]


def instructions_for(name: str) -> list[str]:
    for key, steps in INSTRUCTIONS:
        if key == "" or key.lower() in name.lower():
            return steps
    return []


# --------------------------------------------------------------------------
# Minimal YAML reader for OUR schedule.yaml shape only.
# Supports: a top-level `sources:` list of mappings with scalar string/int
# values. Keeps us dependency-free. If you'd rather use real YAML, install
# PyYAML and swap this out - the rest of the script doesn't care.
# --------------------------------------------------------------------------
def load_sources(path: Path = SCHEDULE) -> list[dict]:
    if not path.exists():
        # Self-heal: seed the default schedule rather than failing.
        paths.ensure_dirs()
        path.write_text(DEFAULT_SCHEDULE_YAML, encoding="utf-8")

    sources: list[dict] = []
    current: dict | None = None
    in_sources = False

    for raw in path.read_text(encoding="utf-8").splitlines():
        # strip trailing comments that start with ' #', but not inside quotes
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        if line.strip() == "sources:":
            in_sources = True
            continue
        if not in_sources:
            continue

        stripped = line.strip()
        if stripped.startswith("- "):
            # start of a new source entry
            if current:
                sources.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if not stripped:
                continue
            # the "- " line itself may carry the first key: value
            _add_kv(current, stripped)
        else:
            if current is None:
                continue
            _add_kv(current, stripped)

    if current:
        sources.append(current)

    # normalize/validate
    out = []
    for s in sources:
        if "name" not in s:
            continue
        try:
            s["every_days"] = int(s.get("every_days", 90))
        except ValueError:
            s["every_days"] = 90
        s.setdefault("url", "")
        s.setdefault("notes", "")
        out.append(s)
    return out


def _add_kv(target: dict, text: str) -> None:
    if ":" not in text:
        return
    key, _, val = text.partition(":")
    key = key.strip()
    val = val.strip()
    # unquote
    if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
        val = val[1:-1]
    target[key] = val


# --------------------------------------------------------------------------
# Request log: one JSON object per line -> {"name":..., "date":"YYYY-MM-DD",
# "note":...}
# --------------------------------------------------------------------------
def load_log() -> list[dict]:
    if not LOG.exists():
        return []
    entries = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def last_request_date(name: str, log: list[dict]) -> dt.date | None:
    dates = []
    for e in log:
        if e.get("name") == name and e.get("date"):
            try:
                dates.append(dt.date.fromisoformat(e["date"]))
            except ValueError:
                pass
    return max(dates) if dates else None


def snooze_until_date(name: str, log: list[dict]) -> dt.date | None:
    """Latest active snooze date for a source, if any.

    A snooze is a log record {"name":..., "snooze_until":"YYYY-MM-DD"}. It
    pushes the next-due date out without pretending a real request happened.
    """
    dates = []
    for e in log:
        if e.get("name") == name and e.get("snooze_until"):
            try:
                dates.append(dt.date.fromisoformat(e["snooze_until"]))
            except ValueError:
                pass
    return max(dates) if dates else None


def status_for(source: dict, log: list[dict]) -> dict:
    now = today()
    last = last_request_date(source["name"], log)
    snooze = snooze_until_date(source["name"], log)
    every = source["every_days"]

    if last is None:
        next_due = now  # never requested -> due now ...
    else:
        next_due = last + dt.timedelta(days=every)

    # ... unless an active snooze pushes it further out.
    if snooze and snooze > next_due:
        next_due = snooze

    return {
        "source": source,
        "last": last,
        "next_due": next_due,
        "days_overdue": (now - next_due).days,
        "due": now >= next_due,
        "snoozed": bool(snooze and snooze >= now and (last is None or snooze > last + dt.timedelta(days=every))),
    }


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
def cmd_due(statuses: list[dict], show_all: bool = False) -> list[dict]:
    due = [s for s in statuses if s["due"]]
    if not due and not show_all:
        print("Nothing due right now. Next up:")
        upcoming = sorted(statuses, key=lambda s: s["next_due"])[:3]
        for s in upcoming:
            print(f"  {s['next_due']}  {s['source']['name']}")
        return due

    rows = statuses if show_all else due
    rows = sorted(rows, key=lambda s: (not s["due"], s["next_due"]))
    header = "ALL SOURCES" if show_all else "DUE NOW"
    print(f"=== {header} ({today()}) ===\n")
    for s in rows:
        src = s["source"]
        last = s["last"].isoformat() if s["last"] else "never"
        if s["due"]:
            tag = "DUE" if s["last"] else "DUE (never requested)"
            od = s["days_overdue"]
            extra = f"  [{od}d overdue]" if od > 0 and s["last"] else ""
        else:
            tag = f"ok, next {s['next_due']}"
            extra = ""
        print(f"[{tag}]{extra}")
        print(f"  {src['name']}")
        print(f"  every {src['every_days']}d | last: {last}")
        if src.get("url"):
            print(f"  {src['url']}")
        if src.get("notes"):
            print(f"  note: {src['notes']}")
        print()
    return due


def cmd_open(statuses: list[dict]) -> None:
    due = cmd_due(statuses)
    urls = [s["source"]["url"] for s in due if s["source"].get("url")]
    # de-dupe while preserving order (several bureaus share one URL)
    seen = set()
    urls = [u for u in urls if not (u in seen or seen.add(u))]
    if not urls:
        print("No URLs to open.")
        return
    print(f"Opening {len(urls)} URL(s) in your browser...")
    for u in urls:
        webbrowser.open(u)


def append_history(line: str) -> None:
    """Append a timestamped, human-readable line to history.log.

    This is the change-tracking trail: every recorded request (and any future
    tracked change) gets one line here, so you can see how things evolved over
    time at a glance - separate from the machine-readable requests.log.
    """
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp}  {line}\n")


MAX_NOTE_LEN = 500


def _clean_note(note: str | None) -> str | None:
    """Make a note safe to store in the one-line-per-entry history.log.

    Collapses any newlines/control chars (prevents log injection / corrupting
    the line-based history) and caps the length (prevents log flooding).
    """
    if not note:
        return None
    # replace any control char (incl. newlines/tabs) with a space
    cleaned = "".join(ch if ch >= " " and ch != "\x7f" else " " for ch in note)
    cleaned = " ".join(cleaned.split()).strip()
    if len(cleaned) > MAX_NOTE_LEN:
        cleaned = cleaned[:MAX_NOTE_LEN].rstrip() + "…"
    return cleaned or None


def record_done(match: str, note: str | None) -> None:
    """Append a 'requested' record for an already-resolved source name.

    Shared by the CLI and the web server so the write/log behavior is
    identical from either entry point. Assumes `match` is a real source name.
    """
    note = _clean_note(note)
    entry = {"name": match, "date": today().isoformat()}
    if note:
        entry["note"] = note
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    append_history("requested: " + match + (f"  ({note})" if note else ""))


def record_snooze(match: str, days: int) -> dt.date:
    """Append a snooze record pushing a source's next-due out by `days`."""
    until = today() + dt.timedelta(days=days)
    entry = {"name": match, "snooze_until": until.isoformat()}
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    append_history(f"snoozed: {match}  until {until.isoformat()} ({days}d)")
    return until


def regenerate_dashboard(sources: list[dict]) -> None:
    """Rebuild dashboard.html from current state (quietly, no stdout)."""
    log = load_log()
    statuses = [status_for(s, log) for s in sources]
    page = render_page(statuses, interactive=False)
    DASHBOARD.write_text(page, encoding="utf-8")


def cmd_done(name: str, note: str | None, sources: list[dict]) -> None:
    names = [s["name"] for s in sources]
    match = _resolve_name(name, names)
    if match is None:
        print(f"No source matches '{name}'. Known sources:")
        for n in names:
            print(f"  - {n}")
        sys.exit(1)
    record_done(match, note)
    print(f"Recorded request for: {match}  ({today()})")
    if note:
        print(f"  note: {note}")
    regenerate_dashboard(sources)  # keep the static dashboard current


def _resolve_name(query: str, names: list[str]) -> str | None:
    # exact match first, then case-insensitive substring
    if query in names:
        return query
    q = query.lower()
    matches = [n for n in names if q in n.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"'{query}' is ambiguous, matches:")
        for m in matches:
            print(f"  - {m}")
        sys.exit(1)
    return None


def cmd_log() -> None:
    log = load_log()
    if not log:
        print("No requests recorded yet.")
        return
    print(f"=== request history ({len(log)} entries) ===\n")
    for e in sorted(log, key=lambda x: x.get("date", "")):
        line = f"{e.get('date','?')}  {e.get('name','?')}"
        if e.get("note"):
            line += f"  - {e['note']}"
        print(line)


# --------------------------------------------------------------------------
# Dashboard: generate a standalone HTML page from the schedule + log.
# No external assets, no network - just open the file in a browser.
# --------------------------------------------------------------------------
import html as _html


def _esc(text: str) -> str:
    return _html.escape(str(text), quote=True)


def _card_html(
    status: dict, interactive: bool = False, snooze_days: int = 30
) -> str:
    src = status["source"]
    name = src["name"]
    url = src.get("url", "")
    due = status["due"]
    last = status["last"].isoformat() if status["last"] else "never"
    next_due = status["next_due"].isoformat()

    if due:
        badge = "DUE" if status["last"] else "DUE · never requested"
        badge_cls = "badge due"
        card_cls = "card due"
        if status["last"] and status["days_overdue"] > 0:
            badge += f" · {status['days_overdue']}d overdue"
    else:
        badge = f"OK · next {next_due}"
        badge_cls = "badge ok"
        card_cls = "card"

    if status.get("snoozed"):
        badge += " · snoozed"

    steps = instructions_for(name)
    steps_html = "\n".join(f"      <li>{s}</li>" for s in steps)

    btn = (
        f'<a class="btn" href="{_esc(url)}" target="_blank" '
        f'rel="noopener noreferrer">Open site ↗</a>'
        if url
        else ""
    )

    if interactive:
        # Live buttons that POST to the local server (see server.py).
        controls = f"""      <div class="btn-row">
        <button class="btn mark-done" data-name="{_esc(name)}">Mark done</button>
        <button class="btn btn-ghost snooze" data-name="{_esc(name)}" data-days="{snooze_days}">Snooze {snooze_days}d</button>
      </div>"""
    else:
        # Static page: show the exact command to run in a terminal.
        controls = (
            f'      <code class="done-hint">python3 recordward.py done '
            f'"{_esc(name)}"</code>'
        )

    return f"""  <section class="{card_cls}" data-due="{str(due).lower()}" data-name="{_esc(name)}">
    <div class="card-head">
      <h2>{_esc(name)}</h2>
      <span class="{badge_cls}">{_esc(badge)}</span>
    </div>
    <div class="meta">
      <span>every {src['every_days']}d</span>
      <span>last requested: {_esc(last)}</span>
    </div>
    <p class="note">{_esc(src.get('notes', ''))}</p>
    <details{' open' if due else ''}>
      <summary>What to do here</summary>
      <ol>
{steps_html}
      </ol>
    </details>
    <div class="actions">
      {btn}
{controls}
    </div>
  </section>"""


def demo_statuses(sources: list[dict]) -> list[dict]:
    """Synthetic statuses for the PUBLIC sample dashboard - no real log.

    Gives a realistic mix of due / ok cards so the shared screenshot looks
    meaningful without exposing anyone's actual request history.
    """
    now = today()
    out = []
    for i, s in enumerate(sources):
        every = s["every_days"]
        if i % 3 == 0:
            # never requested -> due
            out.append(
                {
                    "source": s,
                    "last": None,
                    "next_due": now,
                    "days_overdue": every,
                    "due": True,
                    "snoozed": False,
                }
            )
        else:
            # requested recently -> ok, next due in the future
            last = now - dt.timedelta(days=every // 3)
            next_due = last + dt.timedelta(days=every)
            out.append(
                {
                    "source": s,
                    "last": last,
                    "next_due": next_due,
                    "days_overdue": (now - next_due).days,
                    "due": now >= next_due,
                    "snoozed": False,
                }
            )
    return out


def render_page(
    statuses: list[dict],
    interactive: bool = False,
    demo: bool = False,
    script_nonce: str = "",
    snooze_days: int = 30,
) -> str:
    """Build the dashboard HTML string.

    Shared by the static generator (cmd_dashboard) and the live server. When
    `interactive` is True the cards get Mark-done/Snooze buttons wired to the
    server; otherwise they show the copy-paste CLI command.

    `script_nonce`, when set, is placed on the inline <script> tag so the
    server can serve a strict Content-Security-Policy (script-src 'nonce-...')
    instead of allowing all inline script.
    """
    nonce_attr = f' nonce="{_esc(script_nonce)}"' if script_nonce else ""
    if interactive:
        settings_btn = '<button data-filter="settings" id="settings-btn">Settings</button>'
        settings_panel = """  <div id="settings-panel" class="panel" hidden>
    <h3>Settings</h3>
    <label>Default snooze (days)
      <input type="number" id="set-snooze" min="1" max="3650">
    </label>
    <label class="row"><input type="checkbox" id="set-open"> Open browser on start</label>
    <label class="row"><input type="checkbox" id="set-notify"> Desktop notifications (weekly job)</label>
    <label>Port <input type="number" id="set-port" min="1" max="65535"></label>
    <button class="btn" id="save-settings">Save settings</button>
    <h3>Clean up data</h3>
    <p class="warn">These remove local data and cannot be undone.</p>
    <div class="reset-row">
      <button class="btn btn-ghost reset" data-what="snoozes">Clear snoozes</button>
      <button class="btn btn-ghost reset" data-what="history">Clear history</button>
      <button class="btn btn-ghost reset" data-what="schedule">Reset schedule</button>
      <button class="btn btn-danger reset" data-what="all">Erase everything</button>
    </div>
  </div>"""
    else:
        settings_btn = ""
        settings_panel = ""
    due_count = sum(1 for s in statuses if s["due"])
    # due first, then by next-due date
    ordered = sorted(statuses, key=lambda s: (not s["due"], s["next_due"]))
    cards = "\n".join(
        _card_html(s, interactive=interactive, snooze_days=snooze_days)
        for s in ordered
    )

    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    summary = (
        f"{due_count} of {len(statuses)} source(s) due"
        if due_count
        else "Nothing due right now — nice."
    )

    demo_banner = (
        '<div class="demo-banner">SAMPLE — generated from dummy data, not a '
        "real request history. Run the tool yourself to get live status.</div>"
        if demo
        else ""
    )
    if interactive:
        source_line = "live server — changes save instantly"
        footer_note = (
            "Click <b>Mark done</b> after you request a source, or "
            "<b>Snooze 30d</b> to defer it. This page updates live."
        )
    else:
        source_line = (
            "sample data (<code>--demo</code>)"
            if demo
            else "<code>schedule.yaml</code> + <code>requests.log</code>"
        )
        footer_note = (
            "After you request a source, record it: "
            '<code>python3 recordward.py done "&lt;name&gt;"</code>, then regenerate.'
            "<br>This page reflects a snapshot — it does not update itself live."
        )

    # Client JS: filter toggle always; action buttons only when interactive.
    action_js = (
        """
  async function act(url, body) {
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
    if (!r.ok) { alert('Action failed: ' + r.status); return; }
    location.reload();
  }
  document.querySelectorAll('.mark-done').forEach(b =>
    b.addEventListener('click', () => {
      const note = prompt('Optional note (e.g. what you found):', '') || '';
      act('/api/done', {name: b.dataset.name, note});
    }));
  document.querySelectorAll('.snooze').forEach(b =>
    b.addEventListener('click', () =>
      act('/api/snooze', {name: b.dataset.name, days: parseInt(b.dataset.days,10)})));

  // Settings panel
  const panel = document.getElementById('settings-panel');
  const sbtn = document.getElementById('settings-btn');
  if (sbtn) sbtn.addEventListener('click', async () => {
    const showing = !panel.hidden;
    panel.hidden = showing;
    if (!showing) {
      const r = await fetch('/api/settings');
      const {settings} = await r.json();
      document.getElementById('set-snooze').value = settings.default_snooze_days;
      document.getElementById('set-port').value = settings.port;
      document.getElementById('set-open').checked = settings.open_browser;
      document.getElementById('set-notify').checked = settings.notify;
    }
  });
  const saveBtn = document.getElementById('save-settings');
  if (saveBtn) saveBtn.addEventListener('click', async () => {
    const body = {
      default_snooze_days: parseInt(document.getElementById('set-snooze').value,10),
      port: parseInt(document.getElementById('set-port').value,10),
      open_browser: document.getElementById('set-open').checked,
      notify: document.getElementById('set-notify').checked,
    };
    const r = await fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
    if (r.ok) location.reload(); else alert('Save failed');
  });
  document.querySelectorAll('.reset').forEach(b =>
    b.addEventListener('click', () => {
      const what = b.dataset.what;
      const msg = what === 'all'
        ? 'Erase ALL local data (logs, schedule, settings)? This cannot be undone.'
        : 'Remove ' + what + '? This cannot be undone.';
      if (confirm(msg)) act('/api/reset', {what});
    }));
"""
        if interactive
        else ""
    )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Records Dashboard — recordward</title>
<style>
  :root {{
    --bg: #0f1115; --panel: #171a21; --panel2: #1e222b;
    --text: #e6e8ec; --muted: #9aa3b2; --line: #2a2f3a;
    --due: #ff6b6b; --ok: #4ade80; --accent: #5aa9ff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font: 15px/1.5 system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  }}
  header {{
    padding: clamp(18px, 3vw, 28px) clamp(14px, 4vw, 40px) 16px;
    border-bottom: 1px solid var(--line);
    position: sticky; top: 0; background: var(--bg); z-index: 5;
  }}
  @media (max-width: 480px) {{
    h1 {{ font-size: 18px; }}
    .controls button {{ flex: 1; }}  /* full-width, even buttons on phones */
  }}
  h1 {{ margin: 0 0 4px; font-size: 20px; }}
  .sub {{ color: var(--muted); font-size: 13px; }}
  .summary {{
    margin-top: 10px; font-weight: 600;
    color: {('var(--due)' if due_count else 'var(--ok)')};
  }}
  .controls {{ margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }}
  .controls button {{
    background: var(--panel2); color: var(--text); border: 1px solid var(--line);
    padding: 7px 14px; border-radius: 8px; cursor: pointer; font-size: 13px;
    font-weight: 600; transition: background .12s, color .12s, border-color .12s;
  }}
  .controls button:hover {{ border-color: var(--accent); }}
  /* Clearly show which view you're in: filled accent, not just a tint. */
  .controls button.active {{
    background: var(--accent); color: #06101f; border-color: var(--accent);
  }}
  main {{
    display: grid; gap: 16px;
    padding: 20px clamp(14px, 4vw, 40px) 60px;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
    width: 100%; max-width: 1400px; margin: 0 auto;
  }}
  .card {{
    background: var(--panel); border: 1px solid var(--line);
    border-radius: 12px; padding: 16px; display: flex; flex-direction: column;
  }}
  .card.due {{ border-color: color-mix(in srgb, var(--due) 55%, var(--line)); }}
  .card-head {{ display: flex; justify-content: space-between; gap: 8px;
    align-items: flex-start; }}
  .card-head h2 {{ margin: 0; font-size: 15px; }}
  .badge {{
    font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 999px;
    white-space: nowrap; letter-spacing: .02em;
  }}
  .badge.due {{ background: color-mix(in srgb, var(--due) 22%, transparent);
    color: var(--due); }}
  .badge.ok {{ background: color-mix(in srgb, var(--ok) 18%, transparent);
    color: var(--ok); }}
  .meta {{ display: flex; gap: 14px; flex-wrap: wrap; color: var(--muted);
    font-size: 12px; margin: 10px 0 6px; }}
  .note {{ color: var(--muted); font-size: 13px; margin: 2px 0 10px; }}
  details {{ background: var(--panel2); border: 1px solid var(--line);
    border-radius: 8px; padding: 6px 12px; margin-bottom: 12px; }}
  summary {{ cursor: pointer; font-weight: 600; font-size: 13px; padding: 4px 0; }}
  details ol {{ margin: 8px 0 4px; padding-left: 20px; }}
  details li {{ margin: 6px 0; font-size: 13px; color: var(--text); }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px; }}
  .actions {{ margin-top: auto; display: flex; flex-direction: column; gap: 8px; }}
  .btn {{
    display: inline-block; text-align: center; text-decoration: none;
    background: var(--accent); color: #06101f; font-weight: 700;
    padding: 9px 14px; border-radius: 8px;
  }}
  .btn:hover {{ filter: brightness(1.08); }}
  button.btn {{ border: none; cursor: pointer; font: inherit; }}
  .btn-row {{ display: flex; gap: 8px; }}
  .btn-row .btn {{ flex: 1; }}
  .btn-ghost {{ background: var(--panel2); color: var(--text);
    border: 1px solid var(--line) !important; }}
  .btn-ghost:hover {{ border-color: var(--accent) !important; }}
  .done-hint {{ color: var(--muted); background: var(--bg);
    border: 1px solid var(--line); border-radius: 6px; padding: 6px 8px;
    user-select: all; }}
  footer {{ color: var(--muted); font-size: 12px; text-align: center;
    padding: 0 24px 40px; }}
  footer a {{ color: var(--accent); }}
  .demo-banner {{ background: color-mix(in srgb, var(--accent) 18%, transparent);
    color: var(--accent); border: 1px solid var(--accent); border-radius: 8px;
    padding: 8px 12px; margin-top: 12px; font-size: 12px; font-weight: 600; }}
  .panel {{ margin-top: 14px; padding: 14px; background: var(--panel);
    border: 1px solid var(--line); border-radius: 10px; max-width: 520px; }}
  .panel h3 {{ margin: 6px 0 8px; font-size: 14px; }}
  .panel label {{ display: block; margin: 8px 0; font-size: 13px;
    color: var(--muted); }}
  .panel label.row {{ display: flex; align-items: center; gap: 8px; }}
  .panel input[type=number] {{ width: 90px; margin-left: 8px; background: var(--bg);
    color: var(--text); border: 1px solid var(--line); border-radius: 6px;
    padding: 4px 6px; }}
  .panel .warn {{ color: var(--due); font-size: 12px; margin: 4px 0; }}
  .reset-row {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  .btn-danger {{ background: var(--due) !important; color: #1a0606 !important; }}
</style>
</head>
<body>
<header>
  <h1>Records Dashboard</h1>
  <div class="sub">Request your own background-check / consumer-report records (US · FCRA)</div>
  <div class="summary">{_esc(summary)}</div>
  <div class="controls">
    <button data-filter="due" class="active">Due now</button>
    <button data-filter="all">All sources</button>
    {settings_btn}
  </div>
  {demo_banner}
  {settings_panel}
</header>
<main id="cards">
{cards}
</main>
<footer>
  Generated {generated} from {source_line}.<br>
  {footer_note}<br>
  RecordWard — free software under the
  <a href="https://github.com/Cyb3rF0xX/recordward" target="_blank" rel="noopener noreferrer">AGPLv3</a>
  (<a href="https://github.com/Cyb3rF0xX/recordward" target="_blank" rel="noopener noreferrer">source</a>).
</footer>
<script{nonce_attr}>
  // Filter buttons are the ones with a real filter value (not Settings).
  const buttons = [...document.querySelectorAll('.controls button')]
    .filter(b => b.dataset.filter === 'due' || b.dataset.filter === 'all');
  const cards = () => document.querySelectorAll('#cards .card');
  function apply(filter) {{
    cards().forEach(c => {{
      const due = c.dataset.due === 'true';
      c.style.display = (filter === 'all' || due) ? '' : 'none';
    }});
    buttons.forEach(b => b.classList.toggle('active', b.dataset.filter === filter));
  }}
  buttons.forEach(b => b.addEventListener('click', () => apply(b.dataset.filter)));
  apply('due');
{action_js}
</script>
</body>
</html>
"""
    return page


def cmd_dashboard(
    statuses: list[dict], open_after: bool = False, demo: bool = False
) -> None:
    page = render_page(statuses, interactive=False, demo=demo)
    # Demo output goes to the current directory (the publish script runs it
    # from the repo root); real output goes to the per-OS data dir.
    out_path = (Path.cwd() / "dashboard.demo.html") if demo else DASHBOARD
    out_path.write_text(page, encoding="utf-8")
    due_count = sum(1 for s in statuses if s["due"])
    summary = (
        f"{due_count} of {len(statuses)} source(s) due"
        if due_count
        else "Nothing due right now — nice."
    )
    print(f"Wrote dashboard: {out_path}")
    print(f"  {summary}")
    if open_after:
        webbrowser.open(out_path.as_uri())
        print("  opened in your browser.")
    elif not demo:
        print("  open it with:  xdg-open dashboard.html   (or pass --open)")


# --------------------------------------------------------------------------
# Data management (cleanup / reset)
# --------------------------------------------------------------------------
def reset_history() -> None:
    """Delete the request history and snoozes (requests.log) + history.log."""
    for f in (LOG, HISTORY):
        if f.exists():
            f.unlink()


def reset_snoozes() -> None:
    """Drop only snooze records, keeping real request history intact."""
    if not LOG.exists():
        return
    kept = [e for e in load_log() if not e.get("snooze_until")]
    with LOG.open("w", encoding="utf-8") as fh:
        for e in kept:
            fh.write(json.dumps(e) + "\n")
    append_history("reset: cleared snoozes")


def reset_schedule() -> None:
    """Restore the schedule to the packaged default."""
    paths.ensure_dirs()
    SCHEDULE.write_text(DEFAULT_SCHEDULE_YAML, encoding="utf-8")


def reset_all() -> None:
    """Wipe ALL user data: logs, dashboard, schedule, settings."""
    from . import settings as _settings  # local import avoids a cycle at top

    for f in (LOG, HISTORY, DASHBOARD, SCHEDULE, _settings.paths.settings_file()):
        if f.exists():
            f.unlink()


def cmd_reset(what: str, assume_yes: bool) -> None:
    actions = {
        "history": ("request history and snoozes", reset_history),
        "snoozes": ("snoozes only", reset_snoozes),
        "schedule": ("the schedule (back to defaults)", reset_schedule),
        "all": ("ALL data (logs, schedule, settings)", reset_all),
    }
    label, fn = actions[what]
    if not assume_yes:
        print(f"This will remove {label}. This cannot be undone.")
        resp = input("Type 'yes' to confirm: ").strip().lower()
        if resp != "yes":
            print("Cancelled.")
            return
    fn()
    print(f"Done: removed {label}.")


def cmd_config(key: str | None, value: str | None) -> None:
    from . import settings as _settings

    if key is None:
        # show all
        s = _settings.load()
        print(f"Settings ({_settings.paths.settings_file()}):")
        for k, v in s.items():
            print(f"  {k} = {v}")
        return
    if value is None:
        s = _settings.load()
        print(s.get(key))
        return
    # set: coerce simple types
    coerced: object = value
    if value.lower() in ("true", "false"):
        coerced = value.lower() == "true"
    elif value.isdigit():
        coerced = int(value)
    try:
        _settings.set_value(key, coerced)
        print(f"Set {key} = {coerced}")
    except KeyError:
        valid = ", ".join(_settings.DEFAULT_SETTINGS)
        sys.exit(f"error: unknown setting '{key}'. Valid keys: {valid}")


def cmd_where() -> None:
    print(f"config dir:  {paths.config_dir()}")
    print(f"data dir:    {paths.data_dir()}")
    print(f"schedule:    {SCHEDULE}")
    print(f"requests:    {LOG}")
    print(f"history:     {HISTORY}")
    print(f"dashboard:   {DASHBOARD}")


def _desktop_notify(title: str, body: str) -> None:
    """Fire a desktop notification if a notifier is available (best effort)."""
    import shutil
    import subprocess

    if shutil.which("notify-send"):
        subprocess.run(
            ["notify-send", "-a", "RecordWard", "--", title, body], check=False
        )


def cmd_notify() -> None:
    """Check what's due and fire a desktop notification if anything is.

    This is what the reminder timer runs. It also refreshes the dashboard so
    it's current when the user opens it.
    """
    sources = load_sources(SCHEDULE)
    log = load_log()
    statuses = [status_for(s, log) for s in sources]
    due = [s for s in statuses if s["due"]]
    regenerate_dashboard(sources)
    if not due:
        print("nothing due")
        return
    names = ", ".join(s["source"]["name"].split(" (")[0] for s in due[:4])
    more = f" (+{len(due) - 4} more)" if len(due) > 4 else ""
    _desktop_notify(
        f"RecordWard: {len(due)} record(s) due",
        f"Time to request: {names}{more}",
    )
    print(f"notified: {len(due)} due")


def cmd_reminders(action: str, cadence: str | None) -> None:
    """Show or set the reminder schedule (systemd user timer)."""
    from . import reminders as rem
    from . import settings as _settings

    if action == "status":
        st = rem.status()
        s = _settings.load()
        print(f"preference: {s['reminders']}")
        if not st["supported"]:
            print("scheduling: not supported on this system "
                  "(needs Linux + systemd user timers)")
        else:
            print(f"timer installed: {st['installed']}  active: {st['active']}")
        return

    # action == "set"
    cad = cadence or "off"
    _settings.set_value("reminders", cad)
    try:
        st = rem.apply(cad)
    except (RuntimeError, ValueError) as e:
        print(f"saved preference '{cad}', but could not apply it: {e}")
        return
    if cad == "off":
        print("reminders turned off.")
    else:
        print(f"reminders set to {cad}. timer active: {st.get('active')}")


def cmd_init(assume_yes: bool) -> None:
    """First-run setup: ask about reminders, then record the choice.

    Idempotent and safe to re-run. Marks setup_complete so the wrapper won't
    prompt again. Intended for the console/fallback path; the GUI wrapper has
    its own wizard but calls the same underlying settings + reminders logic.
    """
    from . import reminders as rem
    from . import settings as _settings

    s = _settings.load()
    print("RecordWard first-run setup")
    print("--------------------------")
    if not rem.supported():
        print("Note: automatic reminders need Linux + systemd user timers,")
        print("which aren't available here. You can still use the app; it will")
        print("show what's due whenever you open it.")
        _settings.set_value("setup_complete", True)
        print("Setup complete.")
        return

    print("Reminders check periodically and send a desktop notification when")
    print("records are due. Options: [1] off  [2] weekly  [3] monthly")
    choice = "1"
    if not assume_yes:
        try:
            choice = input("Choose 1/2/3 [1]: ").strip() or "1"
        except EOFError:
            choice = "1"
    cadence = {"1": "off", "2": "weekly", "3": "monthly"}.get(choice, "off")

    _settings.set_value("reminders", cadence)
    try:
        rem.apply(cadence)
    except (RuntimeError, ValueError) as e:
        print(f"(could not apply reminder schedule: {e})")
    _settings.set_value("setup_complete", True)

    if cadence == "off":
        print("No reminders set. You can enable them anytime in Preferences,")
        print("or run:  recordward reminders set weekly")
    else:
        print(f"Reminders on ({cadence}). You'll get a desktop notification when due.")
    print("Setup complete.")


# --------------------------------------------------------------------------
def main(argv: list[str]) -> None:
    bootstrap()  # ensure dirs, migrate legacy files, seed default schedule
    parser = argparse.ArgumentParser(
        description="Local scheduler/log for regularly requesting your own "
        "background-check and consumer-report records (US/FCRA)."
    )
    from . import __version__

    parser.add_argument(
        "--version", action="version", version=f"recordward {__version__}"
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("due", help="show what's due now (default)")
    sub.add_parser("list", help="show every source with next-due date")
    sub.add_parser("open", help="show due items and open their URLs")
    sub.add_parser("log", help="print request history")

    p_dash = sub.add_parser(
        "dashboard", help="generate a standalone HTML dashboard"
    )
    p_dash.add_argument(
        "--open", action="store_true", help="open the dashboard after writing it"
    )
    p_dash.add_argument(
        "--demo",
        action="store_true",
        help="use dummy data and write dashboard.demo.html (for the public copy)",
    )

    p_done = sub.add_parser("done", help="record a request for a source")
    p_done.add_argument("name", help="source name (substring is fine)")
    p_done.add_argument("--note", help="optional note, e.g. what you found")

    p_serve = sub.add_parser("serve", help="run the local web app")
    p_serve.add_argument("--port", type=int, help="port (default from settings)")
    p_serve.add_argument("--no-open", action="store_true")

    p_reset = sub.add_parser("reset", help="remove data / restore defaults")
    p_reset.add_argument(
        "what",
        choices=["history", "snoozes", "schedule", "all"],
        help="what to remove",
    )
    p_reset.add_argument(
        "-y", "--yes", action="store_true", help="skip the confirmation prompt"
    )

    p_config = sub.add_parser("config", help="view or change settings")
    p_config.add_argument("key", nargs="?", help="setting name")
    p_config.add_argument("value", nargs="?", help="new value (omit to read)")

    sub.add_parser("where", help="print where config/data live")
    sub.add_parser("notify", help="check due items and send a desktop notification")
    sub.add_parser("app", help="open the native launcher window (first-run setup)")

    p_init = sub.add_parser("init", help="first-run setup (reminders, etc.)")
    p_init.add_argument("-y", "--yes", action="store_true",
                        help="accept defaults without prompting")

    p_rem = sub.add_parser("reminders", help="show or set the reminder schedule")
    p_rem.add_argument("action", nargs="?", choices=["status", "set"],
                       default="status")
    p_rem.add_argument("cadence", nargs="?", choices=["off", "weekly", "monthly"])

    args = parser.parse_args(argv)
    command = args.command or "due"

    # Commands that don't need the schedule loaded first.
    if command == "reset":
        cmd_reset(args.what, args.yes)
        return
    if command == "config":
        cmd_config(args.key, args.value)
        return
    if command == "where":
        cmd_where()
        return
    if command == "notify":
        cmd_notify()
        return
    if command == "app":
        from . import launcher as _launcher

        _launcher.run()
        return
    if command == "init":
        cmd_init(args.yes)
        return
    if command == "reminders":
        cmd_reminders(args.action, args.cadence)
        return
    if command == "serve":
        from . import server as _server

        _server.run(port=args.port, open_browser=not args.no_open)
        return

    sources = load_sources(SCHEDULE)
    if command == "done":
        cmd_done(args.name, args.note, sources)
        return
    if command == "log":
        cmd_log()
        return

    if command == "dashboard" and args.demo:
        statuses = demo_statuses(sources)
        cmd_dashboard(statuses, open_after=args.open, demo=True)
        return

    log = load_log()
    statuses = [status_for(s, log) for s in sources]

    if command == "due":
        cmd_due(statuses)
    elif command == "list":
        cmd_due(statuses, show_all=True)
    elif command == "open":
        cmd_open(statuses)
    elif command == "dashboard":
        cmd_dashboard(statuses, open_after=args.open)


def _console_main() -> None:
    """Entry point for the installed `recordward` command (no args)."""
    main(sys.argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:])
