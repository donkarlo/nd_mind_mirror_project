"""Regression checks for reliable iPad save retry and Ubuntu editor refresh."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WINDOW = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
).read_text(encoding="utf-8")
RETRY = (
    ROOT
    / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/GraphicSaveRetryController.swift"
).read_text(encoding="utf-8")


def test_normal_ipad_save_retries_until_ack_or_reset() -> None:
    assert "retryDelayNanoseconds: UInt64 = 800_000_000" in RETRY
    assert "_ = sendAction()" in RETRY
    assert "scheduleRetry()" in RETRY
    assert "maximumRetryCount" not in RETRY
    assert "isAwaitingAcknowledgement" in RETRY


def test_each_accepted_graphic_event_forces_source_and_visual_cache_refresh() -> None:
    assert "def _sync_graphic_update_event" in WINDOW
    assert "source_controller.schedule_layout_refresh()" in WINDOW
    assert '"refresh_current_visual_graphics"' in WINDOW
    assert "refresh_visual()" in WINDOW
