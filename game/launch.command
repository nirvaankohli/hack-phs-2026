#!/bin/bash
# Double-click on macOS, or execute from a terminal.
set -e
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/.."
PYTHON="${CLOUDBOUND_PYTHON:-$PWD/.venv/bin/python}"
GODOT="${GODOT_BIN:-/Applications/Godot.app/Contents/MacOS/Godot}"
if [ ! -x "$GODOT" ]; then GODOT="$(command -v godot || true)"; fi
if [ ! -x "$PYTHON" ] || [ -z "$GODOT" ]; then
  echo 'Cloudbound needs Godot 4 and the Python environment described in game/README.md.'
  exit 1
fi
BRIDGE_PID=""
cleanup() { if [ -n "$BRIDGE_PID" ]; then kill "$BRIDGE_PID" 2>/dev/null || true; fi; }
trap cleanup EXIT INT TERM
if ! "$PYTHON" -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8002/health", timeout=1)' 2>/dev/null; then
  "$PYTHON" -m uvicorn game.bridge:app --host 127.0.0.1 --port 8002 &
  BRIDGE_PID=$!
fi
"$GODOT" --headless --path "$PWD/game" --editor --import --quit
"$GODOT" --path "$PWD/game"
