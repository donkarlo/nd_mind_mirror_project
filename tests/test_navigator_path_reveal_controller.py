"""Regression checks for event-driven Navigator path reveal."""

from pathlib import Path


ROOT = Path(__file__).parent.parent
CONTROLLER = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/navigator_path_reveal_controller.py"
).read_text(encoding="utf-8")
STRICT = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/navigator_strict_active_selection_controller.py"
).read_text(encoding="utf-8")


def test_path_reveal_waits_for_real_filesystem_model_signals() -> None:
    assert "directoryLoaded.connect" in CONTROLLER
    assert "rowsInserted.connect" in CONTROLLER
    assert "rootPathChanged.connect" in CONTROLLER
    assert "QTimer" not in CONTROLLER


def test_path_reveal_loads_ancestors_incrementally() -> None:
    assert "canFetchMore(source_index)" in CONTROLLER
    assert "fetchMore(source_index)" in CONTROLLER
    assert "_directory_chain(target, root)" in CONTROLLER


def test_path_reveal_selects_once_target_index_is_valid() -> None:
    assert "ClearAndSelect" in CONTROLLER
    assert "self._tree.setCurrentIndex(view_index)" in CONTROLLER
    assert "PositionAtCenter" in CONTROLLER
    assert "self.path_revealed.emit(str(target))" in CONTROLLER


def test_latest_tab_request_replaces_any_stale_pending_target() -> None:
    reveal = CONTROLLER.split(
        "    def reveal(", 1
    )[1].split(
        "    def _advance_pending_reveal", 1
    )[0]
    assert "self._pending_target = target" in reveal


def test_strict_controller_uses_event_driven_reveal_not_timer_retries() -> None:
    reveal = STRICT.split(
        "    def _reveal_centered", 1
    )[1].split(
        "    def _on_path_revealed", 1
    )[0]
    assert "self._path_reveal_controller.reveal(path)" in reveal
    assert "QTimer" not in STRICT
    assert "_CENTER_DELAYS_MS" not in STRICT
