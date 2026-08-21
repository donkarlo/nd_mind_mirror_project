#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/home/donkarlo/phd-venv/bin/python}"
WORKSPACE="${WORKSPACE:-$HOME/Dropbox/repo}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8766}"
TCP_PORT="${TCP_PORT:-8767}"
IPAD_LISTEN_PORT="${IPAD_LISTEN_PORT:-8768}"
TOKEN="${TOKEN:-}"

echo "ND Graphic bridge launcher"
echo "  project: $PROJECT_ROOT"
echo "  python:  $PYTHON_BIN"
PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - <<'PY'
import nd_mind_mirror.graphic.bridge as bridge
print(f"  version: {bridge.__version__}")
print(f"  module:  {bridge.__file__}")
PY
echo "  websocket: http://$HOST:$PORT / ws://$HOST:$PORT/ws"
echo "  legacy direct TCP fallback: tcp://$HOST:$TCP_PORT"
echo "  reverse iPad transport: Ubuntu scans LAN and connects to iPad tcp/*:$IPAD_LISTEN_PORT"

ARGS=(--workspace "$WORKSPACE" --host "$HOST" --port "$PORT" --tcp-port "$TCP_PORT" --ipad-listen-port "$IPAD_LISTEN_PORT")
if [[ -n "$TOKEN" ]]; then ARGS+=(--token "$TOKEN"); fi
PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" exec "$PYTHON_BIN" -m nd_mind_mirror.graphic.bridge "${ARGS[@]}"
