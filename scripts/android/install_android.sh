#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON_BIN="$HOME/phd-venv/bin/python"
if [ -n "${ND_MIND_MIRROR_PYTHON:-}" ]; then PYTHON_BIN="$ND_MIND_MIRROR_PYTHON"; fi
exec "$PYTHON_BIN" "$ROOT/scripts/android/install_android.py"
