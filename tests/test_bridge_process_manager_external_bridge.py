"""Regression coverage for externally-owned graphic bridge preservation."""

from pathlib import Path


MANAGER = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "nd_mind_mirror"
    / "graphic"
    / "core"
    / "bridge_process_manager.py"
)


def _source() -> str:
    return MANAGER.read_text(encoding="utf-8")


def test_constructor_does_not_kill_existing_bridge() -> None:
    source = _source()
    init_body = source.split("def __init__", 1)[1].split("@classmethod", 1)[0]
    assert "_cleanup_stale_bridges_once()" not in init_body


def test_start_adopts_healthy_bridge_before_stale_cleanup() -> None:
    source = _source()
    body = source.split("def start_if_needed", 1)[1].split("def stop", 1)[0]
    adopt = body.index("_adopt_external_bridge_if_running()")
    cleanup = body.index("_cleanup_stale_bridges_once()")
    assert adopt < cleanup


def test_stop_only_terminates_owned_bridge() -> None:
    source = _source()
    body = source.split("def stop", 1)[1].split(
        "def _adopt_external_bridge_if_running", 1
    )[0]
    assert "if not type(self)._owns_process" in body
