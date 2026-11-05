#!/usr/bin/env bash
# macOS double-clickable launcher. Starts the web app.
# Put this file (or an alias to it) wherever you like; it finds the repo
# relative to its own location if you keep it inside the repo, otherwise it
# falls back to the installed `recordward` command.
cd "$(dirname "$0")/.." 2>/dev/null || true
if command -v recordward >/dev/null 2>&1; then
    exec recordward serve
elif [ -f "server.py" ]; then
    exec python3 server.py
else
    echo "recordward not found. Install with: pipx install git+https://github.com/Cyb3rF0xX/recordward"
    read -r -p "Press Return to close."
fi
