from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent

from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.highlighter.generic.pygments_syntax_highlighter import (
    PygmentsSyntaxHighlighter,
)


class GenericTextEditor(TextEditor):
    """Editable source view for any text file supported by the workspace."""

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
        self._source_update_debounce_ms = 70
        self._source_large_document_threshold_chars = 120000
        self._source_large_document_debounce_ms = 180
        self._content_emit_timer = QTimer(self)
        self._content_emit_timer.setSingleShot(True)
        self._content_emit_timer.timeout.connect(self._flush_content)
        self.apply_settings(app_settings)
        self._highlighter = PygmentsSyntaxHighlighter(
            self.document(),
            self._source_path,
        )
        self.textChanged.connect(self._emit_content)
        self.document().modificationChanged.connect(
            self.modification_changed.emit
        )

    @property
    def source_path(self) -> Path:
        return self._source_path

    def set_source_path(self, source_path: str | Path) -> None:
        self._source_path = Path(source_path).expanduser().resolve()
        self._highlighter.set_source_path(self._source_path)

    def apply_settings(self, app_settings: YamlSettings) -> None:
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
        self.apply_line_height(app_settings.editor_line_height_percent)
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
            current_line_highlight=app_settings.editor_current_line_highlight,
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
            cursor = self.textCursor()
            if cursor.hasSelection():
                cursor.removeSelectedText()
            before = cursor.block().text()[: cursor.positionInBlock()]
            match = re.match(r"^[ \t]*", before)
            prefix = match.group(0) if match else ""
            cursor.insertText("\n" + prefix)
            self.setTextCursor(cursor)
            event.accept()
            return
        super().keyPressEvent(event)

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
        # Language-specific formatters are intentionally not guessed here.
        return

    def _emit_content(self) -> None:
        interval = (
            self._source_large_document_debounce_ms
            if self.document().characterCount() >= self._source_large_document_threshold_chars
            else self._source_update_debounce_ms
        )
        self._content_emit_timer.setInterval(interval)
        self._content_emit_timer.start()

    def _flush_content(self) -> None:
        self.content_changed.emit(self.toPlainText())
