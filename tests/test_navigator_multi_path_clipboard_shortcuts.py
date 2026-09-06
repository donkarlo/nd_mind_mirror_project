"""Regression checks for Navigator multi-path Copy/Cut/Paste shortcut routing."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHORTCUTS = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/navigator_clipboard_shortcut_controller.py"
).read_text(encoding="utf-8")
CONTEXT = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/navigator_multi_path_context_controller.py"
).read_text(encoding="utf-8")
WINDOW = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
).read_text(encoding="utf-8")


def test_file_clipboard_gets_first_refusal_on_ctrl_c_x_v() -> None:
    assert "Qt.Key.Key_C" in SHORTCUTS
    assert "Qt.Key.Key_X" in SHORTCUTS
    assert "Qt.Key.Key_V" in SHORTCUTS
    assert "copy_selected_path()" in SHORTCUTS
    assert "cut_selected_paths()" in SHORTCUTS
    assert "paste_into_selected_path()" in SHORTCUTS
    assert "if not self._context_controller.can_paste()" in SHORTCUTS


def test_context_controller_keeps_extended_selection_and_context_actions() -> None:
    assert "SelectionMode.ExtendedSelection" in CONTEXT
    assert 'menu.addAction("Copy")' in CONTEXT
    assert 'menu.addAction("Cut")' in CONTEXT
    assert 'menu.addAction("Paste")' in CONTEXT
    assert "counter = 0" in CONTEXT
    assert 'f"{base_name}_{counter}{extension}"' in CONTEXT


def test_enhanced_window_installs_navigator_clipboard_router() -> None:
    assert "NavigatorClipboardShortcutController(" in WINDOW
    assert "self._navigator_clipboard_shortcut_controller" in WINDOW
