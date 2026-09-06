"""Regression tests for deterministic Navigator Ctrl+C/Ctrl+X/Ctrl+V routing."""

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent

from nd_mind_mirror.ui.input.navigator_clipboard_key_event_filter import (
    NavigatorClipboardKeyEventFilter,
)


ROOT = Path(__file__).resolve().parents[1]
MULTI_SOURCE = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/navigator_multi_path_context_controller.py"
).read_text(encoding="utf-8")
FILE_SYSTEM_SOURCE = (
    ROOT
    / "src/nd_mind_mirror/ui/panel/file_system/file_system_panel.py"
).read_text(encoding="utf-8")


class _ContextController:
    def __init__(self) -> None:
        self.selected = True
        self.paste_available = True
        self.operations: list[str] = []

    def selected_paths(self):
        return [Path("/tmp/item")] if self.selected else []

    def can_paste(self) -> bool:
        return self.paste_available

    def copy_selected_path(self) -> None:
        self.operations.append("copy")

    def cut_selected_paths(self) -> None:
        self.operations.append("cut")

    def paste_into_selected_path(self) -> None:
        self.operations.append("paste")


def _key(key) -> QKeyEvent:
    return QKeyEvent(
        QEvent.Type.KeyPress,
        key,
        Qt.KeyboardModifier.ControlModifier,
    )


def test_ctrl_c_x_v_dispatch_to_same_operations_as_context_menu() -> None:
    tree = QObject()
    controller = _ContextController()
    event_filter = NavigatorClipboardKeyEventFilter(
        controller,
        tree,
        parent=None,
    )

    assert event_filter.eventFilter(tree, _key(Qt.Key.Key_C))
    assert event_filter.eventFilter(tree, _key(Qt.Key.Key_X))
    assert event_filter.eventFilter(tree, _key(Qt.Key.Key_V))
    assert controller.operations == ["copy", "cut", "paste"]


def test_ctrl_v_falls_through_when_no_file_clipboard_exists() -> None:
    tree = QObject()
    controller = _ContextController()
    controller.paste_available = False
    event_filter = NavigatorClipboardKeyEventFilter(
        controller,
        tree,
        parent=None,
    )

    assert not event_filter.eventFilter(tree, _key(Qt.Key.Key_V))
    assert controller.operations == []


def test_multi_path_controller_disables_qshortcut_clipboard_owners() -> None:
    assert "NavigatorClipboardKeyEventFilter(" in MULTI_SOURCE
    assert 'for name in ("_copy_shortcut", "_paste_shortcut")' in MULTI_SOURCE
    assert "self._cut_shortcut = QShortcut" not in MULTI_SOURCE


def test_existing_clipboard_image_fallback_remains_available() -> None:
    assert "event.key() == Qt.Key.Key_V" in FILE_SYSTEM_SOURCE
    assert "_save_current_clipboard_image" in FILE_SYSTEM_SOURCE
