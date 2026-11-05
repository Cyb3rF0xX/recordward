# Security

RecordWard is a **local, single-user** tool. It stores nothing in the
cloud and makes no outbound network calls. This document describes its threat
model and the hardening in the local web app (`server.py`).

## Threat model

In scope:
- Protecting your local request history from other software and web pages on
  the same machine while the web app is running.
- Not exposing the app to other devices on your network.
- Keeping your personal data out of the public GitHub copy.

Out of scope:
- Multi-user / hosted deployment. This tool is not designed to run as a shared
  service, and doing so would require authentication, transport security, and
  data-protection controls it deliberately does not have.
- Protecting against an attacker who already has your local user account.

## Web app hardening (`server.py`)

- **Localhost bind only.** Listens on `127.0.0.1`, so it is not reachable from
  other machines.
- **Loopback peer check.** Requests are refused unless the client socket is a
  loopback address (defense in depth).
- **Host-header allowlist.** Blocks DNS-rebinding attacks, where a malicious
  site resolves a hostname to `127.0.0.1` to reach the server from your
  browser. Only `localhost`/`127.0.0.1`/`[::1]` (with the bound port) are
  accepted.
- **Strict Content-Security-Policy** with a per-response nonce for the single
  inline script; `default-src 'none'`, no external resources. Plus
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`.
- **State-changing requests are POST + `application/json` only**, which (with
  the Host check) prevents trivial cross-site form/`fetch` abuse.
- **Request-size cap** (64 KiB) and a required, sane `Content-Length` guard
  against memory-exhaustion DoS.
- **Input bounds.** Source names must match a known entry exactly; snooze days
  are clamped to 1–3650; notes are stripped of control characters (prevents
  log injection into the line-based `history.log`) and capped at 500 chars.
- **No version leakage** in the `Server` header.

## Data handling

- `requests.log` and `history.log` contain your personal activity and are
  git-ignored. The publish script never copies them, and runs a sweep that
  aborts if they (or your home path) would be shipped.
- The public repo ships only a **demo** dashboard built from dummy data.

## Reporting

This is a personal utility, not a maintained product. If you fork it and find
an issue, open an issue on your fork.
