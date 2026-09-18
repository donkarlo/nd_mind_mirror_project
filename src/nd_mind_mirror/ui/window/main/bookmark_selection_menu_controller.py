"""Own the Bookmarks menu for canonical character-range bookmarks."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget

from nd_mind_mirror.ui.window.main.bookmark.range.range_bookmark_manager_dialog import (
    RangeBookmarkManagerDialog,
)


class BookmarkSelectionMenuController(QObject):
    """Make top-menu Add/Remove behavior identical to Source/Visual context menus."""

    def __init__(
        self,
        editor_panel,
        bookmarks_menu,
        toggle_action: QAction,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._editor_panel = editor_panel
        self._menu = bookmarks_menu
        self._toggle_action = toggle_action
        self._window = parent
        self._application = QApplication.instance()

        # MainWindow installed the legacy line-bookmark menu first. This final
        # controller is the single owner of Bookmarks, so disconnect that old
        # aboutToShow rebuild instead of racing two menu implementations.
        try:
            self._menu.aboutToShow.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._menu.aboutToShow.connect(self._rebuild_menu)

        try:
            self._toggle_action.triggered.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._toggle_action.triggered.connect(self._execute_context_action)

        if self._application is not None:
            self._application.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        event_type = event.type()
        if event_type not in {
            QEvent.Type.ShortcutOverride,
            QEvent.Type.KeyPress,
        }:
            return super().eventFilter(watched, event)

        if (
            not self._event_matches_shortcut(event, self._toggle_action.shortcut())
            or not self._focus_is_in_current_editor()
        ):
            return super().eventFilter(watched, event)

        event.accept()
        if event_type == QEvent.Type.ShortcutOverride:
            return super().eventFilter(watched, event)
        if not event.isAutoRepeat():
            self._execute_context_action()
        return True

    def _rebuild_menu(self) -> None:
        self._menu.clear()
        state = self._current_state()
        action = str(state.get("action", "none"))
        self._toggle_action.setText(
            str(state.get("label", "Add Bookmark"))
            if action != "none"
            else "Add Bookmark (select text)"
        )
        self._toggle_action.setEnabled(action != "none")
        self._menu.addAction(self._toggle_action)

        entries = list(self._entries())
        if entries:
            self._menu.addSeparator()
            for entry in entries:
                text = " ".join(str(entry.get("text", "")).split())
                if len(text) > 58:
                    text = text[:55] + "…"
                label = text or f"Characters {entry['start_char']}–{entry['end_char']}"
                action_item = self._menu.addAction(
                    f"{label} — {Path(str(entry['path'])).name}"
                )
                action_item.setToolTip(str(entry["path"]))
                action_item.triggered.connect(
                    lambda _checked=False,
                    path=str(entry["path"]),
                    identifier=str(entry["id"]): self._go_to(path, identifier)
                )

        self._menu.addSeparator()
        manage = self._menu.addAction("Manage Bookmarks…")
        manage.triggered.connect(self._show_manager)

    def _current_state(self) -> dict[str, object]:
        editor = self._editor_panel.current_editor()
        provider = getattr(editor, "range_bookmark_menu_context", None)
        if callable(provider):
            return dict(provider())
        return {"action": "none", "label": "Add Bookmark", "bookmark_id": ""}

    def _execute_context_action(self, _checked: bool = False) -> None:
        editor = self._editor_panel.current_editor()
        if editor is None:
            return
        state = self._current_state()
        executor = getattr(editor, "execute_range_bookmark_state", None)
        if callable(executor):
            executor(state)

    def _entries(self):
        for raw_path, bookmarks in self._editor_panel.bookmarks().items():
            for bookmark in bookmarks:
                if "start_char" not in bookmark or "end_char" not in bookmark:
                    continue
                yield {
                    "path": str(raw_path),
                    "id": str(bookmark.get("id", "")),
                    "text": str(bookmark.get("text", "")),
                    "start_char": int(bookmark.get("start_char", 0)),
                    "end_char": int(bookmark.get("end_char", 0)),
                }

    def _show_manager(self) -> None:
        dialog = RangeBookmarkManagerDialog(
            self._entries,
            self._go_to,
            self._remove,
            self._remove_all,
            self._window,
        )
        dialog.exec()

    def _go_to(self, path: str, bookmark_id: str) -> None:
        target = Path(path).expanduser().resolve()
        if not target.is_file():
            return
        opener = getattr(self._window, "_open_path", None)
        if callable(opener):
            opener(str(target))
        QTimer.singleShot(
            0,
            lambda: self._activate_current(target, bookmark_id),
        )

    def _activate_current(self, path: Path, bookmark_id: str) -> None:
        editor = self._editor_panel.current_editor()
        current = self._editor_panel.current_path()
        if editor is None or current is None:
            return
        if Path(current).expanduser().resolve() != path:
            return
        activate = getattr(editor, "activate_range_bookmark", None)
        if callable(activate):
            activate(bookmark_id)

    def _remove(self, path: str, bookmark_id: str) -> None:
        self._editor_panel.remove_range_bookmark(path, bookmark_id)

    def _remove_all(self) -> None:
        self._editor_panel.remove_all_range_bookmarks()

    @staticmethod
    def _event_matches_shortcut(event, sequence: QKeySequence) -> bool:
        if sequence.isEmpty():
            return False
        try:
            return QKeySequence(event.keyCombination()) == sequence
        except (AttributeError, TypeError):
            return False

    def _focus_is_in_current_editor(self) -> bool:
        editor = self._editor_panel.current_editor()
        focus = QApplication.focusWidget()
        if editor is None or focus is None or not isinstance(editor, QWidget):
            return False
        return focus is editor or editor.isAncestorOf(focus)
