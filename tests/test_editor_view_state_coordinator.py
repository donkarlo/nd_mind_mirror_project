"""Regression coverage for deferred editor view-state capture."""

from pathlib import Path


ROOT = Path(__file__).parent.parent
EDITOR_PANEL = (
    ROOT
    / "src/nd_mind_mirror/ui/panel/editor/editor_panel.py"
).read_text(encoding="utf-8")
COORDINATOR = (
    ROOT
    / "src/nd_mind_mirror/ui/panel/editor/view_state/editor_view_state_coordinator.py"
).read_text(encoding="utf-8")


def test_scroll_view_changes_are_deferred_outside_editor_panel_hot_path() -> None:
    body = EDITOR_PANEL.split(
        "    def _on_editor_view_changed", 1
    )[1].split(
        "    def _schedule_editor_view_state", 1
    )[0]

    assert "_schedule_editor_view_state(" in body
    assert "first_visible_source_position(" not in body
    assert "editor.view_state()" not in body
    assert "super()._on_editor_view_changed" not in body


def test_horizontal_scroll_uses_same_view_state_coordinator() -> None:
    assert "self._schedule_editor_view_state(" in EDITOR_PANEL
    assert "resolve_current_view=False" in EDITOR_PANEL


def test_tab_switch_flushes_view_state_synchronously() -> None:
    method = EDITOR_PANEL.split(
        "    def _remember_editor_view_state", 1
    )[1].split(
        "    def _store_editor_view_state", 1
    )[0]

    assert "self._view_state_coordinator.capture_now(" in method
    assert "resolve_current_view=False" in method


def test_coordinator_request_capture_does_no_document_geometry_work() -> None:
    method = COORDINATOR.split(
        "    def request_capture", 1
    )[1].split(
        "    def flush_pending", 1
    )[0]

    assert "view_state(" not in method
    assert "first_visible_source_position(" not in method
    assert "self._timer.start()" in method


def test_coordinator_reuses_visible_location_from_latex_state() -> None:
    method = COORDINATOR.split(
        "    def capture_now", 1
    )[1].split(
        "    def cancel_editor", 1
    )[0]

    assert 'state["visible_source_line"]' in method
    assert 'state["visible_source_column"]' in method
