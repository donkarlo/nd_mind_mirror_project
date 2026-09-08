"""Provide reliable semantic Undo/Redo across Source and Visual editor views."""

from __future__ import annotations

import weakref

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction, QKeyEvent, QTextCursor
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor


class UndoRedoController(QObject):
    """Keep independent source snapshots so Ctrl+Z/Ctrl+Y survive Qt undo-stack resets."""

    _MAX_HISTORY_STEPS = 120

    def __init__(self, parent=None) -> None:
        """Install application-level key/context routing and initialize histories lazily."""
        super().__init__(parent)
        self._histories: dict[int, dict[str, object]] = {}
        self._bound_editors: dict[int, weakref.ReferenceType] = {}
        self._applying: set[int] = set()

        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

        if isinstance(parent, QWidget):
            for editor in parent.findChildren(TextEditor):
                self._bind_view(editor)

    def eventFilter(self, watched, event) -> bool:
        """Route Ctrl+Z/Ctrl+Y and editor context menus through canonical history."""
        if event.type() == QEvent.Type.FocusIn:
            view = self._supported_view(watched)
            if view is not None:
                self._bind_view(view)

        if event.type() == QEvent.Type.Show and isinstance(watched, QMenu):
            self._patch_context_menu(watched)
            return super().eventFilter(watched, event)

        if not isinstance(event, QKeyEvent):
            return super().eventFilter(watched, event)
        if event.type() not in {
            QEvent.Type.ShortcutOverride,
            QEvent.Type.KeyPress,
        }:
            return super().eventFilter(watched, event)

        view = self._supported_view(watched)
        if view is None:
            return super().eventFilter(watched, event)

        self._bind_view(view)
        command = self._command_for(event)
        if command is None:
            return super().eventFilter(watched, event)

        event.accept()
        if event.type() == QEvent.Type.ShortcutOverride:
            return True

        self._run_command(view, command)
        return True

    def _bind_view(self, view: TextEditor | LatexVisualEditor) -> TextEditor:
        """Bind the canonical Source editor once and return it for history operations."""
        canonical = self._canonical_editor(view)
        identity = id(canonical)
        if identity in self._bound_editors:
            return canonical

        self._bound_editors[identity] = weakref.ref(canonical)
        self._histories[identity] = {
            "current": canonical.toPlainText(),
            "undo": [],
            "redo": [],
        }
        editor_ref = weakref.ref(canonical)
        canonical.textChanged.connect(
            lambda ref=editor_ref: self._on_canonical_text_changed(ref)
        )
        if isinstance(canonical, LatexEditor):
            canonical.content_changed.connect(
                lambda _content, ref=editor_ref: self._on_content_changed(ref)
            )
        canonical.destroyed.connect(
            lambda _obj=None, value=identity: self._forget_editor(value)
        )
        return canonical

    def _forget_editor(self, identity: int) -> None:
        """Release snapshot state when its editor tab is destroyed."""
        self._histories.pop(identity, None)
        self._bound_editors.pop(identity, None)
        self._applying.discard(identity)

    def _on_canonical_text_changed(self, editor_ref: weakref.ReferenceType) -> None:
        """Record actual text changes while ignoring formatting-only notifications."""
        editor = editor_ref()
        if editor is None:
            return
        identity = id(editor)
        history = self._histories.get(identity)
        if history is None:
            return

        text = editor.toPlainText()
        current = str(history.get("current", ""))
        if text == current:
            return
        if identity in self._applying:
            history["current"] = text
            return

        undo = history["undo"]
        redo = history["redo"]
        if isinstance(undo, list):
            undo.append(current)
            self._trim_history(undo)
        if isinstance(redo, list):
            redo.clear()
        history["current"] = text

    def _on_content_changed(self, editor_ref: weakref.ReferenceType) -> None:
        """Adopt blocked-signal file loads without erasing identical autosave history."""
        editor = editor_ref()
        if editor is None:
            return
        identity = id(editor)
        history = self._histories.get(identity)
        if history is None:
            return

        text = editor.toPlainText()
        current = str(history.get("current", ""))
        if text == current:
            return
        if identity in self._applying:
            history["current"] = text
            return

        if not editor.document().isModified():
            history["current"] = text
            undo = history["undo"]
            redo = history["redo"]
            if isinstance(undo, list):
                undo.clear()
            if isinstance(redo, list):
                redo.clear()
            return

        undo = history["undo"]
        redo = history["redo"]
        if isinstance(undo, list):
            undo.append(current)
            self._trim_history(undo)
        if isinstance(redo, list):
            redo.clear()
        history["current"] = text

    def _run_command(
        self,
        view: TextEditor | LatexVisualEditor,
        command: str,
    ) -> None:
        """Execute one undo or redo step against shared canonical source history."""
        canonical = self._bind_view(view)
        self._flush_pending_visual_edit(view, canonical)

        history = self._histories.get(id(canonical))
        if history is None:
            return
        undo = history["undo"]
        redo = history["redo"]
        current = str(history.get("current", canonical.toPlainText()))
        if not isinstance(undo, list) or not isinstance(redo, list):
            return

        if command == "redo":
            if not redo:
                return
            target = str(redo.pop())
            undo.append(current)
            self._trim_history(undo)
        else:
            if not undo:
                return
            target = str(undo.pop())
            redo.append(current)
            self._trim_history(redo)

        self._apply_text(canonical, target)

    def _flush_pending_visual_edit(
        self,
        view: TextEditor | LatexVisualEditor,
        canonical: TextEditor,
    ) -> None:
        """Serialize pending Visual typing before undoing the newest keystrokes."""
        if not isinstance(view, LatexVisualEditor):
            return
        if not isinstance(canonical, LatexEditor):
            return
        timer = view._emit_timer
        if not timer.isActive():
            return
        timer.stop()
        view._emit_serialized_source()

    def _apply_text(self, editor: TextEditor, target: str) -> None:
        """Restore one snapshot without clearing editor history and view state."""
        identity = id(editor)
        history = self._histories.get(identity)
        if history is None:
            return

        cursor_position = int(editor.textCursor().position())
        vertical = int(editor.verticalScrollBar().value())
        horizontal = int(editor.horizontalScrollBar().value())
        source_location = None
        if isinstance(editor, LatexEditor):
            source_location = editor.active_source_location()

        self._applying.add(identity)
        try:
            cursor = QTextCursor(editor.document())
            cursor.beginEditBlock()
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.insertText(target)
            cursor.endEditBlock()
            editor.document().setModified(True)
            history["current"] = target

            if isinstance(editor, LatexEditor):
                editor._visual_dirty = True
                line, column = source_location or (1, 1)
                line_count = max(len(target.splitlines()), 1)
                line = max(1, min(int(line), line_count))
                column = max(int(column), 1)

                if editor.edit_mode == "visual":
                    editor._refresh_visual_projection()
                    editor._visual_editor.go_to_source_location(
                        line,
                        column,
                        align_top=False,
                    )
                else:
                    editor._go_to_source_location(
                        line,
                        column,
                        align_top=False,
                    )
                editor.active_cursor_changed.emit()
                editor.active_view_changed.emit()
            else:
                maximum = max(editor.document().characterCount() - 1, 0)
                restored = QTextCursor(editor.document())
                restored.setPosition(max(0, min(cursor_position, maximum)))
                editor.setTextCursor(restored)
                editor.verticalScrollBar().setValue(vertical)
                editor.horizontalScrollBar().setValue(horizontal)
        finally:
            self._applying.discard(identity)

    def _patch_context_menu(self, menu: QMenu) -> None:
        """Replace Undo/Redo only inside a real Source or Visual context menu."""
        view = self._supported_menu_view(menu)
        if view is None:
            return
        canonical = self._bind_view(view)
        history = self._histories.get(id(canonical))
        if history is None:
            return

        for action in list(menu.actions()):
            if self._context_action_command(action.text()) is not None:
                menu.removeAction(action)

        undo = history["undo"]
        redo = history["redo"]
        first = menu.actions()[0] if menu.actions() else None

        undo_action = QAction("Undo", menu)
        undo_action.setEnabled(bool(undo))
        undo_action.triggered.connect(
            lambda _checked=False, item=view: self._run_command(item, "undo")
        )

        redo_action = QAction("Redo", menu)
        redo_action.setEnabled(bool(redo))
        redo_action.triggered.connect(
            lambda _checked=False, item=view: self._run_command(item, "redo")
        )

        if first is None:
            menu.addAction(undo_action)
            menu.addAction(redo_action)
            menu.addSeparator()
            return

        menu.insertAction(first, undo_action)
        menu.insertAction(first, redo_action)
        menu.insertSeparator(first)

    @classmethod
    def _trim_history(cls, stack: list[str]) -> None:
        """Bound memory use while retaining enough undo steps for a long session."""
        overflow = len(stack) - cls._MAX_HISTORY_STEPS
        if overflow > 0:
            del stack[:overflow]

    @staticmethod
    def _canonical_editor(
        view: TextEditor | LatexVisualEditor,
    ) -> TextEditor:
        """Map Visual back to its owning LaTeX Source editor."""
        if isinstance(view, LatexVisualEditor):
            parent = view.parentWidget()
            while parent is not None:
                if isinstance(parent, LatexEditor):
                    return parent
                parent = parent.parentWidget()
        return view

    @staticmethod
    def _supported_menu_view(menu: QMenu) -> TextEditor | LatexVisualEditor | None:
        """Resolve a context menu only through its owning widget hierarchy."""
        current = menu.parentWidget()
        while current is not None:
            if isinstance(current, LatexVisualEditor):
                return current
            if isinstance(current, TextEditor):
                return current
            current = current.parentWidget()
        return None

    @staticmethod
    def _supported_view(watched) -> TextEditor | LatexVisualEditor | None:
        """Resolve key/focus event targets, falling back to the focused editor."""
        candidates = []
        if isinstance(watched, QWidget):
            candidates.append(watched)
        focused = QApplication.focusWidget()
        if isinstance(focused, QWidget):
            candidates.append(focused)

        for candidate in candidates:
            current = candidate
            while current is not None:
                if isinstance(current, LatexVisualEditor):
                    return current
                if isinstance(current, TextEditor):
                    return current
                current = current.parentWidget()
        return None

    @staticmethod
    def _context_action_command(text: str) -> str | None:
        """Recognize standard English/German Undo and Redo labels."""
        label = str(text).replace("&", "").split("\t", 1)[0].strip().casefold()
        if label.startswith("undo") or label.startswith("rückgängig"):
            return "undo"
        if (
            label.startswith("redo")
            or label.startswith("wiederholen")
            or label.startswith("erneut")
        ):
            return "redo"
        return None

    @staticmethod
    def _command_for(event: QKeyEvent) -> str | None:
        """Map Ctrl+Z, Ctrl+Shift+Z, and Ctrl+Y to semantic history commands."""
        modifiers = event.modifiers()
        if not bool(modifiers & Qt.KeyboardModifier.ControlModifier):
            return None
        if bool(
            modifiers
            & (
                Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        ):
            return None

        if event.key() == Qt.Key.Key_Z:
            return (
                "redo"
                if bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
                else "undo"
            )
        if event.key() == Qt.Key.Key_Y:
            return "redo"
        return None
