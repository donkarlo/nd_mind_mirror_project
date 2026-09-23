#!/usr/bin/env bash
# Launch exactly one ND Graphic bridge instance on the canonical transport ports.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/home/donkarlo/phd-venv/bin/python}"
WORKSPACE="${WORKSPACE:-$HOME/Dropbox/repo}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8766}"
TCP_PORT="${TCP_PORT:-8767}"
IPAD_LISTEN_PORT="${IPAD_LISTEN_PORT:-8768}"
TOKEN="${TOKEN:-}"

LOCK_ROOT="${XDG_RUNTIME_DIR:-/tmp}"
LOCK_FILE="$LOCK_ROOT/nd_mind_mirror_graphic_bridge_${UID}.lock"

# A Control Panel restart means "replace the bridge for this workspace".
# Discover and stop the existing workspace bridge before taking the lifetime
# lock; an older bridge launched by this same script still owns that lock.
STALE_PIDS=()
while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    [[ ! -r "/proc/$pid/cmdline" ]] && continue
    cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
    if [[ "$cmdline" == *"-m nd_mind_mirror.graphic.bridge"* ]] \
       && [[ "$cmdline" == *"--workspace $WORKSPACE"* ]]; then
        STALE_PIDS+=("$pid")
    fi
done < <(
    pgrep -u "$(id -u)" -f 'python.*-m[[:space:]]+nd_mind_mirror\.graphic\.bridge' \
        || true
)

if ((${#STALE_PIDS[@]})); then
    echo "Stopping stale ND Graphic bridge process(es): ${STALE_PIDS[*]}"
    kill "${STALE_PIDS[@]}" 2>/dev/null || true

    for _ in {1..30}; do
        alive=0
        for pid in "${STALE_PIDS[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                alive=1
                break
            fi
        done
        ((alive == 0)) && break
        sleep 0.1
    done

    for pid in "${STALE_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "Force-stopping stale bridge PID $pid"
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done
fi

exec 9>"$LOCK_FILE"
if ! flock -w 3 9; then
    echo "ND Graphic bridge is already being launched or is already running."
    exit 0
fi

"$PYTHON_BIN" - "$HOST" "$PORT" "$TCP_PORT" "$IPAD_LISTEN_PORT" <<'PY'
import socket
import sys

host = sys.argv[1]
ports = {
    "websocket": int(sys.argv[2]),
    "legacy TCP": int(sys.argv[3]),
    "iPad listener": int(sys.argv[4]),
}

if len(set(ports.values())) != len(ports):
    raise SystemExit(f"ND Graphic bridge ports must be distinct: {ports}")


def is_available(port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


for label in ("websocket", "legacy TCP"):
    port = ports[label]
    if not is_available(port):
        raise SystemExit(
            f"ND Graphic {label} port {port} is already in use. "
            "Refusing to start a second bridge on a fallback port."
        )
PY

echo "ND Graphic bridge launcher"
echo "  project: $ROOT"
echo "  python:  $PYTHON_BIN"
PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" - <<'PY'
import nd_mind_mirror.graphic.bridge as bridge
print(f"  version: {bridge.__version__}")
print(f"  module:  {bridge.__file__}")
PY
echo "  websocket: http://$HOST:$PORT / ws://$HOST:$PORT/ws"
echo "  legacy direct TCP fallback: tcp://$HOST:$TCP_PORT"
echo "  reverse iPad transport: Ubuntu scans LAN and connects to iPad tcp/*:$IPAD_LISTEN_PORT"

ARGS=(
    --workspace "$WORKSPACE"
    --host "$HOST"
    --port "$PORT"
    --tcp-port "$TCP_PORT"
    --ipad-listen-port "$IPAD_LISTEN_PORT"
)
if [[ -n "$TOKEN" ]]; then
    ARGS+=(--token "$TOKEN")
fi

PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
    exec "$PYTHON_BIN" -m nd_mind_mirror.graphic.bridge "${ARGS[@]}"

