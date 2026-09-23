"""Regression for replacing a bridge that still owns the launcher lock."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = (
    ROOT
    / "src/nd_mind_mirror/graphic/bridge/run_graphic_bridge.sh"
).read_text(encoding="utf-8")


def test_existing_workspace_bridge_is_stopped_before_lifetime_lock() -> None:
    assert LAUNCHER.index("STALE_PIDS=()") < LAUNCHER.index("flock -w 3 9")
    assert "flock -n 9" not in LAUNCHER
    assert 'exec 9>"$LOCK_FILE"' in LAUNCHER
