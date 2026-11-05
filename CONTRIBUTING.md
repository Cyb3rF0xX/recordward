# Contributing

Thanks for your interest. RecordWard is a **local, privacy-first** tool.

## Contribution policy (please read first)

**This project does not currently accept outside code contributions (pull
requests).** This keeps copyright ownership with a single holder, which is
required to offer the project under separate commercial terms in addition to
the AGPLv3 (dual-licensing). Unsolicited PRs will be closed, not out of
disinterest but to keep the licensing clean.

You are very welcome to:
- **open issues** — bug reports, ideas, and questions are appreciated;
- **fork it** under the AGPLv3 and build your own version (the license
  guarantees you that right).

If you have a change you believe belongs upstream, please open an issue to
discuss it first. If the policy changes in future, contributors will be asked
to agree to a Contributor License Agreement so the dual-licensing option is
preserved.

The notes below are for working on your own fork.

## Principles (please respect these)

- **Privacy is non-negotiable.** No telemetry, no analytics, no outbound network
  calls except the user explicitly opening a source's website. If a change
  phones home, it will be declined.
- **Keep the core zero-dependency.** The installed tool uses the Python standard
  library only. A genuinely useful feature that needs a library should be an
  *optional extra*, never a required dependency. Say why in the PR.
- **Security changes need tests.** The web server's guards (localhost bind,
  Host-header validation, CSP, request-size caps, input bounds, log-injection
  resistance) are load-bearing. Changes near them must keep the tests green and
  add tests for new behavior.
- **Boring is good.** Prefer clear, well-understood patterns over clever ones.
  The next reader matters more than brevity.
- **Read the decision record.** `docs/DECISIONS.md` explains the architecture and
  what is intentionally out of scope (hosted SaaS, scraping bureaus, etc.).
  Proposals that conflict with it should argue the case there first.

## Development setup

```bash
git clone https://github.com/Cyb3rF0xX/recordward
cd recordward
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Run the tool from the source tree with `recordward …` (after `pip install -e .`)
or `python recordward.py …` / `python server.py`.

Tests use an isolated data dir via the `RECORDWARD_HOME` env var, so they never
touch your real data.

## Running tests

```bash
python -m unittest discover -s tests -v
```

All tests must pass on your change. CI runs the suite on Linux, macOS, and
Windows across Python 3.9 and 3.12; your PR must be green there too.

## Working on a fork

If you fork it, keep changes consistent with the principles above: tests must
pass (`python -m unittest discover -s tests`), and new behavior — especially
near the server's security guards — needs tests.

## Reporting security issues

Please don't file a public issue for a security problem. Note it privately to
the maintainer first (e.g. a GitHub security advisory on your fork). See
`SECURITY.md` for the threat model and what is in/out of scope.
