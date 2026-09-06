"""Regression checks for Ctrl+W routing from Source and Visual."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/current_editor_tab_close_controller.py"
).read_text(encoding="utf-8")
WINDOW = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
).read_text(encoding="utf-8")


def test_ctrl_w_is_owned_by_active_editor_subtree() -> None:
    assert "QEvent.Type.ShortcutOverride" in CONTROLLER
    assert "QEvent.Type.KeyPress" in CONTROLLER
    assert "Qt.Key.Key_W" in CONTROLLER
    assert "_focus_is_in_current_editor()" in CONTROLLER
    assert "request_close_current_tab()" in CONTROLLER


def test_enhanced_window_installs_close_controller() -> None:
    assert "CurrentEditorTabCloseController(" in WINDOW
    assert "self._current_editor_tab_close_controller" in WINDOW
