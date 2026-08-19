from pathlib import Path
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor

from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.highlighter.yaml.yaml_syntax_highlighter import (
    YamlSyntaxHighlighter,
)


class YamlEditor(TextEditor):
    content_changed = Signal(str)
    modification_changed = Signal(bool)

    def __init__(
        self,
        source_path: str | Path,
        app_settings: YamlSettings,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._source_path = Path(source_path).expanduser().resolve()
        self._indent_size = 4
        self.apply_settings(app_settings)
        self._highlighter = YamlSyntaxHighlighter(self.document())
        self.textChanged.connect(self._emit_content)
        self.document().modificationChanged.connect(
            self.modification_changed.emit
        )

    @property
    def source_path(self) -> Path:
        return self._source_path

    def set_source_path(self, source_path: str | Path) -> None:
        self._source_path = Path(source_path).expanduser().resolve()
        self._indent_size = 4

    def apply_settings(self, app_settings: YamlSettings) -> None:
        self._indent_size = max(int(app_settings.editor_indent_size), 1)
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
            wrap_marker_color=app_settings.editor_wrap_marker_color,
            wrap_marker_margin=app_settings.editor_wrap_marker_margin,
            current_line_highlight=(
                app_settings.editor_current_line_highlight
            ),
            cursor_width=app_settings.editor_cursor_width,
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (
            event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
            and not bool(
                event.modifiers()
                & (
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.AltModifier
                )
            )
        ):
            self._insert_yaml_newline()
            event.accept()
            return

        super().keyPressEvent(event)

    def _insert_yaml_newline(self) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()

        block = cursor.block()
        position_in_block = cursor.position() - block.position()
        before_cursor = block.text()[:position_in_block]
        leading_match = re.match(r"^[ ]*", before_cursor)
        leading = leading_match.group(0) if leading_match else ""
        stripped = before_cursor.strip()

        next_prefix = leading
        if stripped:
            if self._opens_yaml_child(stripped):
                next_prefix += " " * self._indent_size
            elif self._is_sequence_mapping(stripped):
                next_prefix += " " * self._indent_size
            elif stripped.startswith("-") and self._is_sequence_scalar(stripped):
                next_prefix += "- "

        cursor.beginEditBlock()
        cursor.insertText("\n" + next_prefix)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def _opens_yaml_child(self, stripped: str) -> bool:
        content = self._strip_inline_comment(stripped).rstrip()
        if not content:
            return False
        if content.endswith(":"):
            return True
        if content in {"-", "- |", "- >"}:
            return True
        return False

    def _is_sequence_mapping(self, stripped: str) -> bool:
        content = self._strip_inline_comment(stripped).strip()
        if not content.startswith("-"):
            return False
        body = content[1:].strip()
        return bool(re.match(r"[^:]+:\s*.+$", body))

    def _is_sequence_scalar(self, stripped: str) -> bool:
        content = self._strip_inline_comment(stripped).strip()
        if not content.startswith("-"):
            return False
        body = content[1:].strip()
        if not body:
            return False
        # A list item that already starts a mapping should continue as a
        # nested mapping rather than automatically creating another dash.
        if re.match(r"[^:]+:\s*.*$", body):
            return False
        return True

    def _strip_inline_comment(self, text: str) -> str:
        # This deliberately keeps quoted '#' handling simple; indentation is
        # advisory and never changes existing YAML source.
        return text.split(" #", 1)[0]

    def set_content(self, content: str) -> None:
        self.blockSignals(True)
        self.setPlainText(content)
        self.apply_line_height(self._line_height_percent)
        self.document().setModified(False)
        self.blockSignals(False)
        self.content_changed.emit(content)
        self.modification_changed.emit(False)

    def mark_saved(self) -> None:
        self.document().setModified(False)

    def format_document(self) -> None:
        # Settings YAML is intentionally left untouched by LaTeX formatting.
        return

    def _emit_content(self) -> None:
        self.content_changed.emit(self.toPlainText())
