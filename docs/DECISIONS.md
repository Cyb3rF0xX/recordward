# Architecture Decision Record

A living record of the significant decisions for recordward and *why*.
New decisions are appended; superseded ones are marked, not deleted.

---

## Context: who this is for

**Audience:** privacy-minded individuals and anyone interested — i.e. a
**public tool that strangers install and must be able to trust.**

Consequences of that audience (these drive every decision below):

- **Trust is the product.** Users are skeptical by default. They will read the
  source, verify nothing phones home, and judge the project on transparency and
  conservatism far more than on feature count.
- **Install friction kills adoption.** Strangers will not fight a heavy
  toolchain. Low/zero dependencies and a one-line install are features.
- **Contributions and issues will come.** That makes automated tests and CI
  table stakes, not nice-to-haves.
- **Privacy is non-negotiable.** No telemetry, no network calls except the user
  explicitly opening a source's website. Data stays local.

**Explicitly out of scope** (say no on purpose):

- Hosted / multi-user SaaS. Storing other people's records-request data on a
  server creates security and legal obligations this project will not take on.
- Mobile apps. Possible future, but a separate effort; not a near-term goal.
- Automatically logging into bureaus / scraping reports. Against their terms and
  a privacy/liability minefield. The tool reminds and tracks; the user acts.

**Definition of "finished" (v1.0):** a trustworthy, well-tested, documented,
zero-dependency tool that any privacy-minded person can install in one line and
run on Linux/macOS/Windows, with a clear audit trail of what it does.

---

## ADR-001: Keep the core logic UI-agnostic and decoupled from transport

**Decision:** The data model, scheduling logic, settings, and path resolution
live in `recordward.core` / `paths` / `settings`, independent of how the
UI is presented. `render_page()` produces UI; `server.py` is *only* the HTTP
glue.

**Why:** It keeps every UI option open (CLI, web, webview, native) without
touching the logic, and it's what makes future changes cheap and safe. This is
the single most important structural decision and it is already in place.

**Status:** Adopted.

---

## ADR-002: Ship a zero-dependency, stdlib-only core

**Decision:** The installed tool depends on the Python standard library only.
Any richer UI (e.g. a native window) is an **optional extra**, never required.

**Why:** Minimizes install friction and supply-chain surface — both critical for
a skeptical, privacy-focused audience. Fewer dependencies = fewer things to
audit and fewer ways to be compromised.

**Status:** Adopted.

---

## ADR-003: Distribute as a pip/pipx-installable package

**Decision:** `pyproject.toml` + a `recordward` console entry point.
`pipx install git+…` is the recommended path; pip and clone-and-run also work.

**Why:** One definition yields native launcher shims on all three OSes. Standard,
boring, well-understood by the target users.

**Status:** Adopted.

---

## ADR-004: Store user data in per-OS app directories

**Decision:** Schedule, logs, and settings live in the conventional per-OS
location (XDG on Linux, Application Support on macOS, %APPDATA% on Windows),
never inside the installed package. `RECORDWARD_HOME` overrides for portability.

**Why:** Required for a real installable app; makes data survive reinstalls and
makes "reset / erase my data" well-defined and safe.

**Status:** Adopted.

---

## ADR-005: UI transport — local web server now, embedded webview later (optional)

**Decision:** Keep the local HTTP server (`recordward serve`) as the universal,
dependency-free UI that works everywhere including headless/SSH. **If** a
native "app window" experience is wanted, add an **embedded webview (pywebview)**
mode that reuses the same `render_page()` HTML and routes actions through a
JS↔Python bridge instead of HTTP. Do **not** remove the server; the webview is
an additive, optional mode.

**Why:** The web UI gave us cross-platform UI cheaply and remains the most
portable, auditable option. A chunk of the server's hardening (localhost bind,
Host-header check, CSP, request caps) exists *only because it is a server*; a
webview has no open port and sheds most of that surface. But a native toolkit
rewrite (Qt/GTK) would discard the working UI and add heavy deps that work
against this audience, so it is rejected for v1. Electron is rejected (bundles a
second runtime for a Python backend).

**Status:** Implemented in 1.1.0 — the dashboard now renders in a pywebview
window (see ADR-008); `recordward serve` remains the browser/headless fallback.

---

## ADR-006: Tests and CI before new features (the current priority)

**Decision:** Add an automated test suite (stdlib `unittest`) covering the core
logic, data management, and the server's security guards, plus a CI workflow,
**before** any UI migration or new feature.

**Why:** The project currently has **no automated tests** — the biggest real gap
for something strangers will depend on and contribute to. For this audience,
the security behaviors in particular (localhost-only, Host validation, input
bounds, log-injection resistance) must be regression-protected.

**Status:** Done — a unittest suite covers core logic, data management, the
server's security guards, the embedded-CSP behavior, and reminders; CI runs it
on Linux/macOS/Windows across Python 3.9 and 3.12.

---

## ADR-007: Name the project "RecordWard"

**Decision:** The project is named **RecordWard** (brand/display), distributed as
`recordward` on PyPI, imported as `recordward`, with a `recordward` CLI command.

**Why the name:** "record" (your consumer/background records) + "ward" (to guard
/ keep watch) — "guard your own file," which is exactly the tool's purpose.

**Due diligence performed:**
- PyPI: `recordward` / `record-ward` / `record_ward` all unregistered (available).
- GitHub: no existing repos; the `recordward` org/user is available.
- Web search: no commercial product, company, app, or service found using
  "RecordWard".

**Known limitation (important):** This is thorough web/registry availability
diligence, **not** a formal trademark clearance. The official registries
(USPTO TMSearch, WIPO Global Brand Database) are JS apps that could not be
queried programmatically, so a *registered or pending* mark with no web presence
was not ruled out. For a free, non-commercial open-source tool the practical
risk is low (no evidence of any user of the name). **Before any commercial use,
run a formal USPTO/WIPO search (software is Nice Class 9 / 42) or get an
attorney clearance.**

**Status:** Adopted.

---

## ADR-008: Native launcher + first-run setup via pywebview (optional extra)

**Context:** The web app is a browser tab backed by a localhost server. Two
problems follow: (1) there is no real "close" — the server lingers until killed;
(2) a browser-sandboxed page cannot install an OS reminder (systemd timer), so
"turn on reminders" can't actually take effect from the web UI. Users also want
a guided first-run setup and a simple way to launch / change preferences.

**Decision:** Add a **native desktop wrapper** that runs *outside* the browser
sandbox and owns OS-level concerns. It renders the **same HTML/CSS** as the web
dashboard (one design language, already polished) inside a **pywebview** window
— not a re-implemented tkinter UI. The wrapper provides:

- **First-run setup:** on first launch (no settings yet), ask about reminders
  (off / weekly / monthly) + notifications + idle auto-shutdown. If a reminder
  is chosen, install a **systemd user timer**; if declined, record the choice
  and never prompt again.
- **Launcher window** on subsequent runs: Launch app / Preferences / Quit.
- **Preferences** always lists the reminders option with current status and
  instructions to enable it later — a first-run "no" is never a dead end.
- The wrapper installs/removes the systemd timer when reminders change (it can,
  because it is not sandboxed).

**Dependency decision:** pywebview is the project's **first runtime dependency**,
and it is an **optional extra** (`pip install "recordward[app]"`). The CLI and
`recordward serve` remain **zero-dependency**. When the extra is absent, the
wrapper falls back to a **tkinter** window, and if tkinter is also missing, to a
**terminal menu**. This preserves the minimalist promise while delivering a
polished native window for those who want it.

**Why pywebview over tkinter for the primary UI:** tkinter cannot match the
dashboard's visual polish; reusing our HTML avoids maintaining a second, uglier
UI; and pywebview is not sandboxed, so it closes the reminder-install gap.
Verified on this machine: WebKit2 4.1 GI backend is present, so pywebview's
Linux backend works without extra system packages.

**Also:** add **idle auto-shutdown** to the server so the app cleans up after
itself regardless of how it was launched.

**Status:** Implemented in 1.1.0 — first-run wizard, launcher window, systemd
reminder timer, idle auto-shutdown, and the dashboard embedded in the native
window, all with graceful fallback (pywebview → tkinter → terminal).

---

## Rejected / parked

- **Native GUI toolkit (Qt/GTK/wx) for v1** — discards the working web UI, adds
  heavy deps against the grain of a zero-dep tool. Parked.
- **Electron** — second runtime for a Python backend; too heavy. Rejected.
- **Hosted SaaS / accounts** — out of scope (see Context). Rejected for this
  project's identity.
