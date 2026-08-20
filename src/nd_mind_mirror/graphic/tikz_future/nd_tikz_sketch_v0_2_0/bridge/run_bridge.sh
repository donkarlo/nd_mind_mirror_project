#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/home/donkarlo/phd-venv/bin/python}"
WORKSPACE="${WORKSPACE:-$HOME/Dropbox/repo}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8765}"
TOKEN="${TOKEN:-}"

"$PYTHON_BIN" -m pip install -q -e "$HERE"
ARGS=(--workspace "$WORKSPACE" --host "$HOST" --port "$PORT")
if [[ -n "$TOKEN" ]]; then
  ARGS+=(--token "$TOKEN")
fi
PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}" exec "$PYTHON_BIN" -m nd_tikz_bridge "${ARGS[@]}"
