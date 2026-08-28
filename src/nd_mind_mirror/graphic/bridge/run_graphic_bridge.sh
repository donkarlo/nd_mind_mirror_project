#!/usr/bin/env bash
# Resolve collision-safe local bridge ports and launch the Python graphic bridge.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/home/donkarlo/phd-venv/bin/python}"
WORKSPACE="${WORKSPACE:-$HOME/Dropbox/repo}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8766}"
TCP_PORT="${TCP_PORT:-8767}"
IPAD_LISTEN_PORT="${IPAD_LISTEN_PORT:-8768}"
TOKEN="${TOKEN:-}"

REQUESTED_PORT="$PORT"
REQUESTED_TCP_PORT="$TCP_PORT"
read -r PORT TCP_PORT < <(
    "$PYTHON_BIN" - "$HOST" "$PORT" "$TCP_PORT" "$IPAD_LISTEN_PORT" <<'PY'
import socket
import sys

host = sys.argv[1]
websocket_start = int(sys.argv[2])
tcp_start = int(sys.argv[3])
ipad_listener_port = int(sys.argv[4])


def is_available(port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    bind_host = host
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((bind_host, port))
        except OSError:
            return False
    return True


def next_available(start: int, reserved: set[int]) -> int:
    for candidate in range(start, 65536):
        if candidate in reserved:
            continue
        if is_available(candidate):
            return candidate
    raise SystemExit(f"No free TCP port available at or above {start}")


websocket_reserved = {ipad_listener_port}
if tcp_start != websocket_start:
    websocket_reserved.add(tcp_start)
websocket_port = next_available(websocket_start, websocket_reserved)
tcp_port = next_available(tcp_start, {ipad_listener_port, websocket_port})
print(websocket_port, tcp_port)
PY
)

echo "ND Graphic bridge launcher"
echo "  project: $ROOT"
echo "  python:  $PYTHON_BIN"
PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - <<'PY'
import nd_mind_mirror.graphic.bridge as bridge
print(f"  version: {bridge.__version__}")
print(f"  module:  {bridge.__file__}")
PY
if [[ "$PORT" != "$REQUESTED_PORT" ]]; then
    echo "  websocket port $REQUESTED_PORT busy -> using $PORT"
fi
if [[ "$TCP_PORT" != "$REQUESTED_TCP_PORT" ]]; then
    echo "  legacy TCP port $REQUESTED_TCP_PORT busy -> using $TCP_PORT"
fi
echo "  websocket: http://$HOST:$PORT / ws://$HOST:$PORT/ws"
echo "  legacy direct TCP fallback: tcp://$HOST:$TCP_PORT"
echo "  reverse iPad transport: Ubuntu scans LAN and connects to iPad tcp/*:$IPAD_LISTEN_PORT"

ARGS=(--workspace "$WORKSPACE" --host "$HOST" --port "$PORT" --tcp-port "$TCP_PORT" --ipad-listen-port "$IPAD_LISTEN_PORT")
if [[ -n "$TOKEN" ]]; then ARGS+=(--token "$TOKEN"); fi
PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" exec "$PYTHON_BIN" -m nd_mind_mirror.graphic.bridge "${ARGS[@]}"
