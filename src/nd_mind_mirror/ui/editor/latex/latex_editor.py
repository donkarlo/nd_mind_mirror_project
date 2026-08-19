from pathlib import Path
import re

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QCompleter

from nd_mind_mirror.core.clipboard.image.clipboard_image_saver import (
    ClipboardImageSaver,
)
from nd_mind_mirror.core.completion.latex.latex_shortcut_provider import (
    LatexShortcut,
    LatexShortcutProvider,
)
from nd_mind_mirror.core.latex.formatting.latex_formatter import (
    LatexFormatter,
)
from nd_mind_mirror.core.latex.indentation.latex_indentation_engine import (
    LatexIndentationEngine,
)
from nd_mind_mirror.core.latex.direction.latex_text_direction_resolver import (
    LatexTextDirectionResolver,
    TextDirection,
)
from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.editor.latex.latex_shortcut_popup import (
    LatexShortcutPopup,
)
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
        self._direction_resolver = LatexTextDirectionResolver()
        self.set_block_direction_resolver(
            self._resolve_qt_layout_direction
        )
        self._shortcuts: list[LatexShortcut] = []
        self._shortcut_min_prefix_length = 2
        self._active_shortcut_prefix = ""
        self._shortcut_popup = LatexShortcutPopup(self)

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
        self._direction_resolver.set_preferences(
            mode=app_settings.editor_latex_text_direction,
            persian_ratio_threshold=(
                app_settings.editor_latex_rtl_persian_ratio
            ),
        )
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
        self._shortcut_min_prefix_length = (
            app_settings.shortcut_min_prefix_length
        )
        self._shortcuts = LatexShortcutProvider(
            app_settings.latex_shortcuts_file_path
        ).load()
        self._shortcut_popup.hide()

        self._indentation.set_indent_size(
            app_settings.editor_indent_size
        )
        self._formatter.set_indent_size(
            app_settings.editor_indent_size
        )

    def _resolve_qt_layout_direction(
        self,
        line: str,
    ) -> Qt.LayoutDirection:
        direction = self._direction_resolver.resolve(line)
        if direction == TextDirection.RIGHT_TO_LEFT:
            return Qt.LayoutDirection.RightToLeft
        return Qt.LayoutDirection.LeftToRight

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

    def bold_selection(self) -> bool:
        return self._wrap_selected_text(
            prefix="\\textbf{",
            suffix="}",
        )

    def highlight_selection(self, color: str) -> bool:
        latex_color = str(color).strip()
        if not latex_color:
            return False

        cursor = self.textCursor()
        if not cursor.hasSelection():
            return False

        selected = cursor.selectedText().replace("\u2029", "\n")
        lines = selected.split("\n")
        replacement_lines = [
            self._wrap_line_preserving_tex_comment(
                line,
                prefix=f"\\colorbox{{{latex_color}}}{{",
                suffix="}",
            )
            for line in lines
        ]
        replacement = "\n".join(replacement_lines)

        cursor.beginEditBlock()
        cursor.insertText(replacement)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.setFocus()
        return True

    def _wrap_selected_text(
        self,
        prefix: str,
        suffix: str,
    ) -> bool:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return False

        selected = cursor.selectedText().replace("\u2029", "\n")
        lines = selected.split("\n")
        replacement = "\n".join(
            self._wrap_line_preserving_tex_comment(
                line,
                prefix=prefix,
                suffix=suffix,
            )
            for line in lines
        )
        cursor.beginEditBlock()
        cursor.insertText(replacement)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.setFocus()
        return True

    @staticmethod
    def _split_unescaped_tex_comment(line: str) -> tuple[str, str]:
        for index, char in enumerate(line):
            if char != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                return line[:index], line[index:]
        return line, ""

    @classmethod
    def _wrap_line_preserving_tex_comment(
        cls,
        line: str,
        prefix: str,
        suffix: str,
    ) -> str:
        if not line:
            return ""
        code, comment = cls._split_unescaped_tex_comment(line)
        if not code:
            return comment
        return prefix + code + suffix + comment

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
        if (
            event.key() == Qt.Key.Key_B
            and bool(
                event.modifiers()
                & Qt.KeyboardModifier.ControlModifier
            )
            and not bool(
                event.modifiers()
                & (
                    Qt.KeyboardModifier.AltModifier
                    | Qt.KeyboardModifier.MetaModifier
                )
            )
        ):
            self.bold_selection()
            event.accept()
            return

        latex_popup = self._completer.popup()

        if self._shortcut_popup.isVisible():
            if event.key() == Qt.Key.Key_Down:
                self._shortcut_popup.move_selection(1)
                event.accept()
                return
            if event.key() == Qt.Key.Key_Up:
                self._shortcut_popup.move_selection(-1)
                event.accept()
                return
            if event.key() in (
                Qt.Key.Key_Enter,
                Qt.Key.Key_Return,
                Qt.Key.Key_Tab,
            ):
                shortcut = self._shortcut_popup.selected_shortcut()
                if shortcut is not None:
                    self._insert_shortcut(shortcut)
                event.accept()
                return
            if event.key() == Qt.Key.Key_Escape:
                self._shortcut_popup.hide()
                event.accept()
                return

        if (
            latex_popup.isVisible()
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
            self._shortcut_popup.hide()
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

        if prefix.startswith("\\"):
            self._shortcut_popup.hide()

            if len(prefix) < 2 and not force_completion:
                latex_popup.hide()
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
            return

        latex_popup.hide()
        self._update_shortcut_popup()

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
        line_start = text.rfind("\n", 0, original_position) + 1
        current_line = text[line_start:original_position]

        # Enter preserves only indentation that is already present in the
        # source line. It must not invent a new hierarchy indent because the
        # editor cannot know whether the next line will be LaTeX code or
        # Persian/English prose. Ctrl+Shift+F remains responsible for full
        # hierarchy formatting.
        indentation = self._indentation.leading_whitespace(
            current_line
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

    def _shortcut_prefix(self) -> str:
        cursor = self.textCursor()
        position = cursor.position()
        block_text = cursor.block().text()
        offset = position - cursor.block().position()
        left = block_text[:offset]

        match = re.search(
            r"[A-Za-z][A-Za-z0-9_-]*$",
            left,
        )
        return match.group(0) if match else ""

    def _update_shortcut_popup(self) -> None:
        prefix = self._shortcut_prefix()
        if len(prefix) < self._shortcut_min_prefix_length:
            self._active_shortcut_prefix = ""
            self._shortcut_popup.hide()
            return

        folded = prefix.casefold()
        matches = [
            shortcut
            for shortcut in self._shortcuts
            if shortcut.trigger.casefold().startswith(folded)
        ]

        if not matches:
            self._active_shortcut_prefix = ""
            self._shortcut_popup.hide()
            return

        # Remember exactly what the user typed (for example ``lis``).
        # The selected trigger may be longer (``list``), but only the typed
        # prefix must be replaced.
        self._active_shortcut_prefix = prefix
        self._shortcut_popup.set_matches(matches)
        self._shortcut_popup.show_under_cursor()

    def _insert_shortcut(
        self,
        shortcut: LatexShortcut,
    ) -> None:
        prefix = self._active_shortcut_prefix or self._shortcut_prefix()
        if not prefix:
            self._shortcut_popup.hide()
            return

        cursor = self.textCursor()
        line_text = cursor.block().text()
        offset = cursor.position() - cursor.block().position()

        # Delete the exact logical characters typed immediately before the
        # caret. Do not use QTextCursor.Left here: in an RTL paragraph Left
        # is a visual movement and can select the wrong characters.
        logical_start_offset = max(offset - len(prefix), 0)
        if line_text[logical_start_offset:offset] != prefix:
            prefix = self._shortcut_prefix()
            if not prefix:
                self._active_shortcut_prefix = ""
                self._shortcut_popup.hide()
                return
            logical_start_offset = max(offset - len(prefix), 0)

        before_prefix = line_text[:logical_start_offset]
        base_indent_match = re.match(r"^[ \t]*", before_prefix)
        base_indent = (
            base_indent_match.group(0)
            if base_indent_match is not None
            else ""
        )

        cursor.beginEditBlock()
        block_start = cursor.block().position()
        insertion_end = cursor.position()
        insertion_start = block_start + logical_start_offset
        cursor.setPosition(insertion_start)
        cursor.setPosition(
            insertion_end,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.removeSelectedText()

        replacement = shortcut.replacement
        marker = LatexShortcutProvider.CURSOR_MARKER
        marker_index = replacement.find(marker)
        if marker_index >= 0:
            replacement = replacement.replace(marker, "", 1)

        replacement = replacement.replace(
            "\n",
            "\n" + base_indent,
        )

        insertion_start = cursor.position()
        cursor.insertText(replacement)
        cursor.endEditBlock()

        if marker_index >= 0:
            marker_prefix = shortcut.replacement[:marker_index].replace(
                marker,
                "",
            )
            marker_prefix = marker_prefix.replace(
                "\n",
                "\n" + base_indent,
            )
            cursor.setPosition(
                insertion_start + len(marker_prefix)
            )

        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self._active_shortcut_prefix = ""
        self._shortcut_popup.hide()
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
