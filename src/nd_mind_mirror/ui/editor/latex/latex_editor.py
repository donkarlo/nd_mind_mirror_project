from pathlib import Path
import re

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QCompleter

from nd_mind_mirror.core.clipboard.image.clipboard_image_saver import (
    ClipboardImageSaver,
)
from nd_mind_mirror.core.latex.formatting.latex_formatter import (
    LatexFormatter,
)
from nd_mind_mirror.core.latex.indentation.latex_indentation_engine import (
    LatexIndentationEngine,
)
from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.highlighter.latex.latex_syntax_highlighter import (
    LatexSyntaxHighlighter,
)


class LatexEditor(TextEditor):
    content_changed = Signal(str)
    modification_changed = Signal(bool)

    def __init__(
        self,
        completions: list[str],
        source_path: str | Path,
        app_settings: YamlSettings,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._source_path = Path(
            source_path
        ).expanduser().resolve()
        self._indentation = LatexIndentationEngine(
            app_settings.editor_indent_size
        )
        self._formatter = LatexFormatter(
            app_settings.editor_indent_size
        )
        self._image_saver = ClipboardImageSaver()

        self.apply_settings(app_settings)

        self.setPlaceholderText(
            "Open a .tex file from the filesystem or File -> Open."
        )

        self._highlighter = LatexSyntaxHighlighter(
            self.document()
        )

        self._completer = QCompleter(
            completions,
            self,
        )
        self._completer.setWidget(self)
        self._completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self._completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseSensitive
        )
        self._completer.activated.connect(
            self._insert_completion
        )

        self.textChanged.connect(
            self._emit_content
        )
        self.document().modificationChanged.connect(
            self.modification_changed.emit
        )

    @property
    def source_path(self) -> Path:
        return self._source_path

    def set_source_path(
        self,
        source_path: str | Path,
    ) -> None:
        self._source_path = Path(
            source_path
        ).expanduser().resolve()

    def apply_settings(
        self,
        app_settings: YamlSettings,
    ) -> None:
        self.apply_font_preferences(
            font_family=app_settings.editor_font_family,
            font_size=app_settings.editor_font_size,
            font_min_size=app_settings.editor_font_min_size,
            font_max_size=app_settings.editor_font_max_size,
        )
        self.apply_line_height(
            app_settings.editor_line_height_percent
        )
        self.apply_visual_preferences(
            soft_wrap=app_settings.editor_soft_wrap,
            wrap_marker=app_settings.editor_wrap_marker,
            wrap_marker_color=(
                app_settings.editor_wrap_marker_color
            ),
            wrap_marker_margin=(
                app_settings.editor_wrap_marker_margin
            ),
            current_line_highlight=(
                app_settings.editor_current_line_highlight
            ),
            cursor_width=app_settings.editor_cursor_width,
        )
        self._indentation.set_indent_size(
            app_settings.editor_indent_size
        )
        self._formatter.set_indent_size(
            app_settings.editor_indent_size
        )

    def set_content(self, content: str) -> None:
        self.blockSignals(True)
        self.setPlainText(content)
        self.apply_line_height(
            self._line_height_percent
        )
        self.document().setModified(False)
        self.blockSignals(False)

        self.content_changed.emit(content)
        self.modification_changed.emit(False)

    def mark_saved(self) -> None:
        self.document().setModified(False)

    def format_document(self) -> None:
        source = self.toPlainText()
        formatted = self._formatter.format(source)

        if formatted == source:
            return

        current_cursor = self.textCursor()
        old_position = current_cursor.position()

        replacement_cursor = QTextCursor(
            self.document()
        )
        replacement_cursor.beginEditBlock()
        replacement_cursor.select(
            QTextCursor.SelectionType.Document
        )
        replacement_cursor.insertText(formatted)
        replacement_cursor.endEditBlock()

        restored_cursor = self.textCursor()
        restored_cursor.setPosition(
            min(
                old_position,
                max(
                    self.document().characterCount() - 1,
                    0,
                ),
            )
        )
        self.setTextCursor(restored_cursor)
        self.ensureCursorVisible()
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        popup = self._completer.popup()

        if (
            popup.isVisible()
            and event.key()
            in (
                Qt.Key.Key_Enter,
                Qt.Key.Key_Return,
                Qt.Key.Key_Escape,
                Qt.Key.Key_Tab,
                Qt.Key.Key_Backtab,
            )
        ):
            event.ignore()
            return

        if (
            event.key()
            in (
                Qt.Key.Key_Enter,
                Qt.Key.Key_Return,
            )
            and not bool(
                event.modifiers()
                & (
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.AltModifier
                    | Qt.KeyboardModifier.MetaModifier
                )
            )
        ):
            self._insert_smart_new_line()
            event.accept()
            return

        force_completion = (
            event.key() == Qt.Key.Key_Space
            and bool(
                event.modifiers()
                & Qt.KeyboardModifier.ControlModifier
            )
        )

        if not force_completion:
            super().keyPressEvent(event)

        prefix = self._completion_prefix()

        if not prefix.startswith("\\"):
            popup.hide()
            return

        if len(prefix) < 2 and not force_completion:
            popup.hide()
            return

        self._completer.setCompletionPrefix(prefix)
        self._completer.popup().setCurrentIndex(
            self._completer.completionModel().index(
                0,
                0,
            )
        )

        rectangle = self.cursorRect()
        rectangle.setWidth(
            self._completer.popup().sizeHintForColumn(0)
            + self._completer.popup()
            .verticalScrollBar()
            .sizeHint()
            .width()
        )
        self._completer.complete(rectangle)

    def insertFromMimeData(
        self,
        source: QMimeData,
    ) -> None:
        image_path = self._image_saver.save(
            source,
            self._source_path,
        )

        if image_path is None:
            super().insertFromMimeData(source)
            return

        relative_path = image_path.relative_to(
            self._source_path.parent
        ).as_posix()
        self._insert_figure(relative_path)

    def _insert_smart_new_line(self) -> None:
        cursor = self.textCursor()
        text = self.toPlainText()
        original_position = cursor.position()
        indentation = self._indentation.indent_for_new_line(
            text,
            original_position,
        )

        cursor.beginEditBlock()
        cursor.insertText("\n")
        cursor.insertText(indentation)
        cursor.endEditBlock()

        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self.setFocus()

    def _insert_figure(
        self,
        relative_image_path: str,
    ) -> None:
        cursor = self.textCursor()
        text = self.toPlainText()
        position = cursor.position()
        line_start = text.rfind("\n", 0, position) + 1
        line_before_cursor = text[line_start:position]
        base_indent = self._indentation.indentation_at_cursor(
            text,
            position,
        )
        inner_indent = base_indent + self._indentation.indent_unit

        if line_before_cursor.strip():
            prefix = "\n" + base_indent
        elif base_indent.startswith(line_before_cursor):
            prefix = base_indent[len(line_before_cursor):]
        else:
            prefix = base_indent

        figure = (
            f"{prefix}\\begin{{figure}}[H]\n"
            f"{inner_indent}\\centering\n"
            f"{inner_indent}\\includegraphics[width=0.9\\textwidth]"
            f"{{{relative_image_path}}}\n"
            f"{base_indent}\\end{{figure}}"
        )

        cursor.beginEditBlock()
        cursor.insertText(figure)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self.setFocus()

    def _completion_prefix(self) -> str:
        cursor = self.textCursor()
        position = cursor.position()

        block_text = cursor.block().text()
        offset = position - cursor.block().position()
        left = block_text[:offset]

        match = re.search(
            r"\\[A-Za-z@]*$",
            left,
        )

        return match.group(0) if match else ""

    def _insert_completion(
        self,
        completion: str,
    ) -> None:
        prefix = self._completer.completionPrefix()

        if not completion.startswith(prefix):
            return

        suffix = completion[len(prefix):]

        cursor = self.textCursor()
        cursor.insertText(suffix)
        self.setTextCursor(cursor)

    def _emit_content(self) -> None:
        self.content_changed.emit(
            self.toPlainText()
        )
