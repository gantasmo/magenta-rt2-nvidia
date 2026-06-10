#!/bin/bash
# macOS / Linux one-click entry (RunPod cloud GUI). Double-click (may need: chmod +x MRT2-Studio.command).
cd "$(dirname "$0")/cloud"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "Python 3 is required. Opening download page…"
  (open https://www.python.org/downloads/ 2>/dev/null || xdg-open https://www.python.org/downloads/ 2>/dev/null)
  read -r -p "Install Python, then press Enter to retry…" _
  PY="$(command -v python3 || command -v python)"
  [ -z "$PY" ] && exit 1
fi
exec "$PY" launcher.py
