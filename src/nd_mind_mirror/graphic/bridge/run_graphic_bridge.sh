#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/home/donkarlo/phd-venv/bin/python}"
WORKSPACE="${WORKSPACE:-$HOME/Dropbox/repo}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8766}"
TOKEN="${TOKEN:-}"
ARGS=(--workspace "$WORKSPACE" --host "$HOST" --port "$PORT")
if [[ -n "$TOKEN" ]]; then ARGS+=(--token "$TOKEN"); fi
PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" exec "$PYTHON_BIN" -m nd_mind_mirror.graphic.bridge "${ARGS[@]}"
