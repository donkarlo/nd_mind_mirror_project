"""Regression checks for Navigator clipboard routing and default-path sharing."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KEY_FILTER = (
    ROOT
    / "src/nd_mind_mirror/ui/input/navigator_clipboard_key_event_filter.py"
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
    assert "Qt.Key.Key_C" in KEY_FILTER
    assert "Qt.Key.Key_X" in KEY_FILTER
    assert "Qt.Key.Key_V" in KEY_FILTER
    assert "copy_selected_path()" in KEY_FILTER
    assert "cut_selected_paths()" in KEY_FILTER
    assert "paste_into_selected_path()" in KEY_FILTER


def test_context_controller_keeps_extended_selection_and_context_actions() -> None:
    assert "SelectionMode.ExtendedSelection" in CONTEXT
    assert 'menu.addAction("Copy")' in CONTEXT
    assert 'menu.addAction("Cut")' in CONTEXT
    assert 'menu.addAction("Paste")' in CONTEXT
    assert 'copy_menu.addAction("Copy from Default Path")' in CONTEXT
    assert "_copy_selected_default_rooted_paths" in CONTEXT
    assert 'f"/{relative_text}"' in CONTEXT
    assert "counter = 0" in CONTEXT
    assert 'f"{base_name}_{counter}{extension}"' in CONTEXT


def test_enhanced_window_uses_single_multi_path_context_controller() -> None:
    assert "NavigatorMultiPathContextController.replace(" in WINDOW
    assert "NavigatorClipboardShortcutController" not in WINDOW
