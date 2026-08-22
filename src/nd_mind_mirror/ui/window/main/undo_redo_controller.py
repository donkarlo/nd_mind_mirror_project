"""Normalize editor undo/redo across keyboard layouts and context menus."""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor


class UndoRedoController(QObject):
    """Provide one semantic Undo/Redo path for Source and Visual editors."""

    _MAX_STACK_STEPS = 128

    def __init__(self, parent=None) -> None:
        """Install one application event filter for keys and editor context menus."""
        super().__init__(parent)
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        """Route keyboard and context-menu Undo/Redo through semantic history."""
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

        editor = self._supported_editor(watched)
        if editor is None:
            return super().eventFilter(watched, event)

        command = self._command_for(event)
        if command is None:
            return super().eventFilter(watched, event)

        event.accept()
        if event.type() == QEvent.Type.ShortcutOverride:
            return True

        self._run_command(editor, command)
        return True

    def _patch_context_menu(self, menu: QMenu) -> None:
        """Replace Qt's one-stack-step Undo/Redo actions in editor menus."""
        editor = self._supported_editor(menu)
        if editor is None:
            return

        for action in menu.actions():
            command = self._context_action_command(action.text())
            if command is None:
                continue

            try:
                action.triggered.disconnect()
            except (RuntimeError, TypeError):
                pass

            action.triggered.connect(
                lambda _checked=False, item=editor, value=command:
                self._run_command(item, value)
            )
            document = editor.document()
            action.setEnabled(
                document.isUndoAvailable()
                if command == "undo"
                else document.isRedoAvailable()
            )

    @staticmethod
    def _context_action_command(text: str) -> str | None:
        """Recognize standard English/German Undo and Redo menu labels."""
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

    @classmethod
    def _run_command(
        cls,
        editor: TextEditor | LatexVisualEditor,
        command: str,
    ) -> None:
        """Undo/redo one visible edit while skipping presentation-only entries.

        QTextDocument records block-format changes in the same undo stack as
        text edits. Mind Mirror reapplies line height, RTL/LTR direction and
        hanging wrap indentation after source changes, so a normal Qt undo can
        consume only an invisible formatting command. This method keeps moving
        through those entries until the editor's semantic content changes.
        """
        document = editor.document()
        undoing = command == "undo"
        available = (
            document.isUndoAvailable
            if undoing
            else document.isRedoAvailable
        )
        operation = editor.undo if undoing else editor.redo

        if not available():
            return

        initial_state = cls._semantic_state(editor)
        for _ in range(cls._MAX_STACK_STEPS):
            if not available():
                break
            operation()
            if cls._semantic_state(editor) != initial_state:
                break

        editor.viewport().update()

    @staticmethod
    def _semantic_state(editor: TextEditor | LatexVisualEditor) -> str:
        """Return source text for Source and rich HTML for semantic Visual edits."""
        if isinstance(editor, LatexVisualEditor):
            return editor.toHtml()
        return editor.toPlainText()

    @staticmethod
    def _supported_editor(watched) -> TextEditor | LatexVisualEditor | None:
        """Resolve a watched widget, menu parent, or focused child to an editor."""
        candidates = []
        if isinstance(watched, QWidget):
            candidates.append(watched)
        focused = QApplication.focusWidget()
        if focused is not None and focused not in candidates:
            candidates.append(focused)

        for candidate in candidates:
            widget = candidate
            while widget is not None:
                if isinstance(widget, (TextEditor, LatexVisualEditor)):
                    return widget
                widget = widget.parentWidget()
        return None

    @staticmethod
    def _command_for(event: QKeyEvent) -> str | None:
        """Map native-aware Qt keys plus QWERTZ fallbacks to undo or redo."""
        if event.matches(QKeySequence.StandardKey.Undo):
            return "undo"
        if event.matches(QKeySequence.StandardKey.Redo):
            return "redo"

        modifiers = event.modifiers()
        control = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        forbidden = bool(
            modifiers
            & (
                Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )
        if not control or forbidden:
            return None

        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        text = event.text()
        if text == "\x1a":
            return "redo" if shift else "undo"
        if text == "\x19" and not shift:
            return "redo"

        key = event.key()
        if key == Qt.Key.Key_Z:
            return "redo" if shift else "undo"
        if key == Qt.Key.Key_Y and not shift:
            return "redo"

        native = int(event.nativeVirtualKey())
        if native in {ord("z"), ord("Z")}:
            return "redo" if shift else "undo"
        if native in {ord("y"), ord("Y")} and not shift:
            return "redo"
        return None
