#!/usr/bin/env bash
# notify.sh - run the checker and, if anything is due, pop a desktop
# notification. Meant to be called by the systemd user timer, but you can
# run it by hand too.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prefer the installed `recordward` command; fall back to the repo launcher.
if command -v recordward >/dev/null 2>&1; then
    RUN=(recordward)
else
    RUN=("$(command -v python3)" "$HERE/recordward.py")
fi

# Keep the dashboard fresh on every run, so it always reflects current status.
"${RUN[@]}" dashboard >/dev/null 2>&1 || true

# Count how many sources are due by asking the tool.
DUE_OUTPUT="$("${RUN[@]}" due 2>/dev/null || true)"

if printf '%s' "$DUE_OUTPUT" | grep -q '^\[DUE'; then
    COUNT="$(printf '%s\n' "$DUE_OUTPUT" | grep -c '^\[DUE' || true)"
    BODY="$(printf '%s\n' "$DUE_OUTPUT" | grep -A1 '^\[DUE' | grep '^  [A-Za-z]' | sed 's/^  /- /')"
    if command -v notify-send >/dev/null 2>&1; then
        # `--` ends option parsing so a body starting with "-" is safe.
        notify-send -a "recordward" -u normal -- \
            "Records to request ($COUNT due)" \
            "${BODY:-Run: python3 recordward.py due}"
    fi
    # Always echo too, so `journalctl --user -u recordward` shows it.
    echo "[$(date -Is)] $COUNT source(s) due:"
    printf '%s\n' "$DUE_OUTPUT"
else
    echo "[$(date -Is)] nothing due."
fi
