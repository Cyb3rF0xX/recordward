# RecordWard

**Guard your own file.**

[![CI](https://github.com/Cyb3rF0xX/recordward/actions/workflows/ci.yml/badge.svg)](https://github.com/Cyb3rF0xX/recordward/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Core dependencies](https://img.shields.io/badge/core%20dependencies-none-brightgreen)

RecordWard is a small local tool that reminds you to **regularly request your
own background-check and consumer-report records** (US / FCRA), and keeps a log
of what you've requested and when.

It does **not** log into any site or pull data for you. Those sites require
your authentication and don't offer consumer APIs. This tool handles the part
that's easy to forget: *what should I request, when is it due again, and what
did I find last time.*

## Why these sources

There's no single "someone ran a background check on me" feed, so you cover the
main channels on a rotation:

- **The 3 credit bureaus** via [AnnualCreditReport.com](https://www.annualcreditreport.com)
  (the only federally authorized free site; free weekly since 2023). Their
  **Inquiries** section reveals many employment/background pulls as soft
  inquiries.
- **LexisNexis** consumer disclosure, which backs a lot of screening data.
- **Employment screeners** (Checkr, Sterling, HireRight, First Advantage,
  Accurate) — request your *file disclosure* **and** the *list of recipients in
  the past 2 years* (FCRA entitles you to who pulled a report for employment
  purposes).
- **CFPB's list** of consumer reporting companies, reviewed yearly to catch any
  new screener relevant to you.

Note: some checks pull directly from court/public records and leave no trace you
can see. No tool can alert you to those. For near-real-time signal, also turn on
**new-inquiry alerts** in free credit monitoring (Credit Karma, Experian, or
your bank/card).

## Layout

| Path | What it is |
|------|------------|
| `recordward/` | The Python package (CLI, web server, settings, data paths). |
| `recordward.py` / `server.py` | Thin launchers so a clone runs without installing. |
| `pyproject.toml` | Packaging — enables `pipx install` and the `recordward` command. |
| `launchers/` | Clickable launchers for macOS (`.command`) and Windows (`.pyw`). |
| `recordward.service` / `.timer` | systemd **user** units to run the weekly check. |
| `notify.sh` | Runs the checker and pops a desktop notification if anything is due. |

Your **data** (schedule, logs, settings) lives in a per-OS app directory, not in
this folder — run `recordward where` to see exactly where.

## Install

```bash
pipx install git+https://github.com/Cyb3rF0xX/recordward
```

That puts a `recordward` command on your PATH (Linux/macOS/Windows, Python 3.9+,
zero dependencies). For the polished native launcher window, add the optional
extra:

```bash
pipx install "git+https://github.com/Cyb3rF0xX/recordward#egg=recordward[app]"
# or, from a clone:  pip install ".[app]"
```

The `[app]` extra pulls in `pywebview` for a native window; the CLI and web app
work without it. See [INSTALL.md](INSTALL.md) for pip, clone-and-run, clickable
launchers, and standalone-binary options.

## Native launcher & first-run setup

```bash
recordward app
```

Opens a small native window (via `pywebview` if installed, else a simple
dialog, else a terminal menu). On **first run** it walks you through reminder
setup; after that it offers **Launch app / Preferences / Quit**. Because it runs
outside the browser sandbox, it can actually install the reminder schedule —
something the web UI alone can't do.

## Reminders

RecordWard can notify you when records come due, via a **systemd user timer**
(Linux; no sudo needed). Set it up in the launcher's first-run wizard or from
the CLI:

```bash
recordward reminders set weekly    # or monthly, or off
recordward reminders status        # show current schedule + whether it's active
recordward notify                  # what the timer runs: check + desktop notification
```

If you decline reminders at first run, you're never nagged again — the option
stays in Preferences with instructions to enable it later.

## Usage

If you installed it, use the `recordward` command:

```bash
recordward serve            # the interactive web app (recommended)
recordward due              # what's due right now
recordward list             # every source + next-due date
recordward open             # show due items AND open their URLs
recordward log              # your request history
recordward done Equifax     # record a request (resets its clock)
recordward done Checkr --note "got file, no new recipients"
recordward where            # show where your data/config live
```

Running from a clone without installing? Use `python3 recordward.py <command>` and
`python3 server.py` — same behavior.

The `name` for `done` is a substring match, so `done lexis` works — you don't
have to type the full name.

## Settings and cleanup

Your schedule, logs, and settings live in a per-OS app directory (run
`recordward where` to see exactly where), so they survive reinstalls.

```bash
recordward config                        # show current settings
recordward config default_snooze_days 60 # change one
recordward reset snoozes                 # clear snoozes
recordward reset history                 # clear request history
recordward reset schedule                # restore the default schedule
recordward reset all                     # erase ALL local data
```

All of this is also available in the web app's **Settings** panel (open the app
and click **Settings**), including the data-cleanup buttons.

## The web app (interactive, cross-platform)

For a clickable experience with no terminal, run the local web app:

```bash
recordward serve              # starts http://127.0.0.1:8765 and opens it
recordward serve --port 9000
recordward serve --no-open    # don't auto-open the browser
```

It serves the dashboard with working **Mark done**, **Snooze**, and **Settings**
(including data cleanup) — click them in the browser and changes save instantly.
Stop the server with Ctrl+C.

- **Cross-platform:** standard library only (Python's `http.server`), so it runs
  the same on Windows, macOS, and Linux. Nothing extra to install.
- **Private and hardened:** binds to `127.0.0.1` (localhost) only, validates the
  `Host` header (blocks DNS-rebinding), serves a strict Content-Security-Policy
  with a per-response nonce, caps request size, and bounds all inputs. Your data
  never leaves the machine. See [SECURITY.md](SECURITY.md) for the full threat
  model.

### Launch it like an app

Clickable launchers are included for each OS (see [INSTALL.md](INSTALL.md)):

- **Linux:** `cp recordward.desktop ~/.local/share/applications/`, then
  search your app menu for "recordward".
- **macOS:** double-click `launchers/recordward.command`.
- **Windows:** double-click `launchers/recordward.pyw` (no console window).

## The visual dashboard (static file)

If you just want a snapshot file (e.g. to screenshot or share), generate a
static HTML dashboard instead of running the server:

```bash
recordward dashboard          # writes dashboard.html to your data dir
recordward dashboard --open   # writes it AND opens in your browser
```

Run `recordward where` to find the generated `dashboard.html`.

Each source is a card showing:
- its status badge (**DUE** in red, or **OK · next <date>** in green),
- its cadence and when you last requested it,
- an **Open site ↗** button that takes you straight to the right URL,
- a collapsible **"What to do here"** with step-by-step instructions tailored to
  that source (credit bureaus → check the Inquiries section; screeners → request
  your file + 2-year recipient list; etc.),
- the exact `done` command to copy once you've made the request.

A **Due now / All sources** toggle at the top filters the cards. The page is a
static snapshot — it reflects the state when you generated it, so regenerate
after you record requests (`done`) or edit `schedule.yaml`. It's fully
self-contained (inline CSS/JS, no network), so it works offline and nothing
leaves your machine.

## Automating the reminder (systemd user timer)

This runs weekly, and the tool itself decides what's actually due based on each
source's cadence.

```bash
# 1. Link the units into your user systemd dir
#    (adjust the source path to wherever you cloned the repo)
mkdir -p ~/.config/systemd/user
ln -sf ~/recordward/recordward.service ~/.config/systemd/user/
ln -sf ~/recordward/recordward.timer   ~/.config/systemd/user/

# 2. Reload and enable the timer
systemctl --user daemon-reload
systemctl --user enable --now recordward.timer

# 3. Check it
systemctl --user list-timers recordward.timer
systemctl --user start recordward.service   # fire once now to test
journalctl --user -u recordward.service     # see output
```

To have timers run even when you're not logged in (optional):

```bash
sudo loginctl enable-linger "$USER"
```

To stop/remove:

```bash
systemctl --user disable --now recordward.timer
```

### Prefer cron instead of systemd?

Add this line with `crontab -e` (runs Mondays at 10:00):

```cron
# cron does not expand ~, so use an absolute path (or $HOME).
0 10 * * 1 $HOME/recordward/notify.sh
```

## Change tracking

Two logs accumulate as you use the tool:

- `requests.log` — machine-readable (one JSON object per request); drives the
  due/ok status.
- `history.log` — a human-readable, timestamped trail of what happened (each
  recorded request adds a line). This is your at-a-glance change history.

Both are personal and are git-ignored.

The dashboard also **stays current automatically**: recording a request
regenerates `dashboard.html`, and the weekly `notify.sh` regenerates it on every
run. You can still regenerate manually anytime with `recordward dashboard`.

## Customizing the schedule

Your schedule lives at the path shown by `recordward where` (the config dir). Edit
it to:
- change `every_days` to request more or less often,
- remove screeners you'll never deal with,
- add a new source by copying an existing block (keep `name`, `url`,
  `every_days`).

Restore the shipped default anytime with `recordward reset schedule`.

The Linux desktop notification needs `notify-send`. If a run shows "nothing
due," that's expected once you've recorded recent requests.

## Contributing

Issues and PRs are welcome — please read [CONTRIBUTING.md](CONTRIBUTING.md) and
the architecture notes in [docs/DECISIONS.md](docs/DECISIONS.md) first. This is a
privacy-first, zero-dependency tool, and contributions are judged against that.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for what changed in each release.

## License

[GNU AGPLv3](LICENSE) (or later) — see [COPYRIGHT](COPYRIGHT) for the notice.
This is strong copyleft: anyone who modifies RecordWard and distributes it **or
runs it as a network service** must release their source under the AGPL too. The
copyright holder reserves the right to offer the software under separate
commercial terms.
