"""Provide an editable YAML source editor with configurable indentation and syntax highlighting."""

from pathlib import Path
import re

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor

from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.core.yaml.formatting.yaml_formatter import YamlFormatter
from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.highlighter.yaml.yaml_syntax_highlighter import (
    YamlSyntaxHighlighter,
)


class YamlEditor(TextEditor):
    """Edit YAML while using the shared source-editor indentation settings."""

    content_changed = Signal(str)
    modification_changed = Signal(bool)

    def __init__(
        self,
        source_path: str | Path,
        app_settings: YamlSettings,
        parent=None,
    ) -> None:
        """Initialize a YAML editor for one source path."""
        super().__init__(parent)
        self._source_path = Path(source_path).expanduser().resolve()
        self._indent_size = 4
        self._formatter = YamlFormatter(self._indent_size)
        self._source_update_debounce_ms = 70
        self._source_large_document_threshold_chars = 120000
        self._source_large_document_debounce_ms = 180
        self._content_emit_timer = QTimer(self)
        self._content_emit_timer.setSingleShot(True)
        self._content_emit_timer.timeout.connect(self._flush_content)
        self.apply_settings(app_settings)
        self._highlighter = YamlSyntaxHighlighter(self.document())
        self.textChanged.connect(self._emit_content)
        self.document().modificationChanged.connect(
            self.modification_changed.emit
        )

    @property
    def source_path(self) -> Path:
        """Return the canonical source path."""
        return self._source_path

    def set_source_path(self, source_path: str | Path) -> None:
        """Update the source path without changing configured indentation."""
        self._source_path = Path(source_path).expanduser().resolve()

    def apply_settings(self, app_settings: YamlSettings) -> None:
        """Apply shared editor and YAML indentation preferences."""
        self._indent_size = max(int(app_settings.editor_indent_size), 1)
        if hasattr(self, "_formatter"):
            self._formatter.set_indent_size(self._indent_size)
        self._source_update_debounce_ms = app_settings.editor_source_update_debounce_ms
        self._source_large_document_threshold_chars = app_settings.editor_source_large_document_threshold_chars
        self._source_large_document_debounce_ms = app_settings.editor_source_large_document_debounce_ms
        if hasattr(self, "_content_emit_timer"):
            self._content_emit_timer.setInterval(self._source_update_debounce_ms)
        self.apply_font_preferences(
            font_family=app_settings.editor_font_family,
            font_size=app_settings.editor_source_font_size,
            font_min_size=app_settings.editor_font_min_size,
            font_max_size=app_settings.editor_font_max_size,
        )
        self.apply_indentation_preferences(
            tab_size=app_settings.editor_tab_size,
            guides_enabled=app_settings.editor_indent_guides_enabled,
            guide_color=app_settings.editor_indent_guide_color,
            guide_width=app_settings.editor_indent_guide_width,
        )
        self.apply_line_height(
            app_settings.editor_line_height_percent
        )
        self.apply_content_padding(
            top=app_settings.editor_source_padding_top,
            left=app_settings.editor_source_padding_left,
            right=app_settings.editor_source_padding_right,
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
        """Insert smart YAML indentation on Enter and delegate other source keys."""
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
        """Insert a newline with context-aware YAML indentation."""
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
        """Return whether a YAML line opens an indented child block."""
        content = self._strip_inline_comment(stripped).rstrip()
        if not content:
            return False
        if content.endswith(":"):
            return True
        if content in {"-", "- |", "- >"}:
            return True
        return False

    def _is_sequence_mapping(self, stripped: str) -> bool:
        """Return whether a sequence item contains an inline mapping entry."""
        content = self._strip_inline_comment(stripped).strip()
        if not content.startswith("-"):
            return False
        body = content[1:].strip()
        return bool(re.match(r"[^:]+:\s*.+$", body))

    def _is_sequence_scalar(self, stripped: str) -> bool:
        """Return whether a sequence item should continue with another dash."""
        content = self._strip_inline_comment(stripped).strip()
        if not content.startswith("-"):
            return False
        body = content[1:].strip()
        if not body:
            return False
        if re.match(r"[^:]+:\s*.*$", body):
            return False
        return True

    def _strip_inline_comment(self, text: str) -> str:
        """Strip the simple inline-comment form used by indentation heuristics."""
        return text.split(" #", 1)[0]

    def set_content(self, content: str) -> None:
        """Replace editor text while marking the loaded content as saved."""
        self.blockSignals(True)
        self.setPlainText(content)
        self.apply_line_height(self._line_height_percent)
        self.document().setModified(False)
        self.blockSignals(False)
        self.content_changed.emit(content)
        self.modification_changed.emit(False)

    def mark_saved(self) -> None:
        """Mark the current document state as saved."""
        self.document().setModified(False)

    def format_document(self) -> None:
        """Normalize YAML indentation as one undoable edit while preserving selection."""
        source = self.toPlainText()
        formatted = self._formatter.format(source)
        if formatted == source:
            return

        active = self.textCursor()
        anchor_location = self._location_for_position(active.anchor())
        position_location = self._location_for_position(active.position())

        edit = QTextCursor(self.document())
        edit.beginEditBlock()
        edit.select(QTextCursor.SelectionType.Document)
        edit.insertText(formatted)
        edit.endEditBlock()

        restored = QTextCursor(self.document())
        restored.setPosition(self._position_for_location(anchor_location))
        restored.setPosition(
            self._position_for_location(position_location),
            QTextCursor.MoveMode.KeepAnchor,
        )
        self.setTextCursor(restored)
        self.ensureCursorVisible()

    def _location_for_position(self, position: int) -> tuple[int, int]:
        """Convert an absolute QTextDocument position to zero-based line/column."""
        maximum = max(self.document().characterCount() - 1, 0)
        bounded = max(0, min(int(position), maximum))
        block = self.document().findBlock(bounded)
        if not block.isValid():
            return 0, 0
        return block.blockNumber(), bounded - block.position()

    def _position_for_location(self, location: tuple[int, int]) -> int:
        """Convert a saved zero-based line/column to a bounded document position."""
        line, column = location
        block = self.document().findBlockByNumber(max(int(line), 0))
        if not block.isValid():
            return max(self.document().characterCount() - 1, 0)
        return block.position() + min(max(int(column), 0), len(block.text()))

    def _emit_content(self) -> None:
        """Debounce content emission according to document size."""
        interval = (
            self._source_large_document_debounce_ms
            if self.document().characterCount() >= self._source_large_document_threshold_chars
            else self._source_update_debounce_ms
        )
        self._content_emit_timer.setInterval(interval)
        self._content_emit_timer.start()

    def _flush_content(self) -> None:
        """Emit the current plain YAML source."""
        self.content_changed.emit(self.toPlainText())
