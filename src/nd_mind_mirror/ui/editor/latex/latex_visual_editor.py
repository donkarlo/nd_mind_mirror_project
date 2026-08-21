from __future__ import annotations

import html
import re
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer, Signal, QUrl
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QFont,
    QKeyEvent,
    QImage,
    QWheelEvent,
    QTextBlockFormat,
    QTextBlockUserData,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextImageFormat,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QTextEdit,
)

from nd_mind_mirror.core.completion.latex.latex_shortcut_provider import LatexShortcut
from nd_mind_mirror.ui.editor.latex.raw_latex_snippet_editor import RawLatexSnippetEditor


_RAW_LATEX_PROPERTY = int(QTextFormat.Property.UserProperty) + 101
_LATEX_TEXT_COLOR_PROPERTY = int(QTextFormat.Property.UserProperty) + 102
_LATEX_HIGHLIGHT_PROPERTY = int(QTextFormat.Property.UserProperty) + 103
_VISUAL_HEADING_PROPERTY = int(QTextFormat.Property.UserProperty) + 104


class _BlockMeta(QTextBlockUserData):
    def __init__(
        self,
        *,
        kind: str = "paragraph",
        command: str = "",
        raw: str = "",
        display: str = "",
        depth: int = 0,
        source_line: int = 0,
        source_segments: list[tuple[int, str]] | None = None,
    ) -> None:
        super().__init__()
        self.kind = kind
        self.command = command
        self.raw = raw
        self.display = display
        self.depth = max(int(depth), 0)
        self.source_line = max(int(source_line), 0)
        self.source_segments = list(source_segments or [])


class LatexVisualEditor(QTextEdit):
    """Source-backed visual editor for the common LaTeX writing subset.

    The canonical document remains LaTeX source in ``LatexEditor``.  This
    widget is only a projection of the document body.  Supported structures
    are converted to QTextDocument formatting; unsupported LaTeX is kept as
    an explicit raw-code block, so switching to visual mode never silently
    discards source that it does not understand.
    """

    source_changed = Signal(str)
    graphic_requested = Signal(int, int)

    _HEADING_COMMANDS = (
        "part",
        "chapter",
        "section",
        "subsection",
        "subsubsection",
        "paragraph",
        "subparagraph",
    )
    _HEADING_SIZES = {
        "part": 24,
        "chapter": 22,
        "section": 20,
        "subsection": 18,
        "subsubsection": 16,
        "paragraph": 15,
        "subparagraph": 14,
    }
    _HEADING_LEVELS = {
        command: index + 1 for index, command in enumerate(_HEADING_COMMANDS)
    }
    _LATEX_TO_QCOLOR = {
        "red": "#b42318",
        "blue": "#175cd3",
        "green": "#067647",
        "orange": "#b54708",
        "violet": "#6938ef",
        "purple": "#6938ef",
        "cyan": "#087e8b",
        "black": "#101828",
        "gray": "#667085",
        "grey": "#667085",
    }
    _SIMPLE_MATH_DISPLAY = {
        r"\alpha": "α",
        r"\beta": "β",
        r"\gamma": "γ",
        r"\delta": "δ",
        r"\epsilon": "ε",
        r"\theta": "θ",
        r"\lambda": "λ",
        r"\mu": "μ",
        r"\pi": "π",
        r"\rho": "ρ",
        r"\sigma": "σ",
        r"\tau": "τ",
        r"\phi": "φ",
        r"\psi": "ψ",
        r"\omega": "ω",
    }
    _HIGHLIGHT_TO_QCOLOR = {
        "yellow!20": "#fff6bf",
        "green!15": "#dcf4dc",
        "blue!12": "#dfefff",
        "cyan!12": "#ddf7f7",
        "orange!18": "#ffe8c7",
        "red!12": "#ffe0e0",
        "violet!12": "#eee1f7",
        "black!8": "#ededed",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptRichText(True)
        self.setPlaceholderText("Visual LaTeX editor")
        self.setStyleSheet(
            "QTextEdit { background: #ffffff; border: 0; padding: 0; }"
        )
        self._prefix = ""
        self._source_path: Path | None = None
        self._suffix = ""
        self._loading = False
        # A Visual document must never be allowed to serialize back into the
        # canonical source before it has actually been populated from source.
        # This is especially important during construction/settings changes,
        # because QTextDocument format changes can emit QTextEdit.textChanged.
        self._has_loaded_source = False
        self._source_generation = 0
        self._raw_completions: list[str] = []
        self._raw_shortcuts: list[LatexShortcut] = []
        self._raw_shortcut_min_prefix_length = 2
        self._configured_font_family = ""
        self._configured_font_size = 16
        self._configured_font_min_size = 6
        self._configured_font_max_size = 40
        self._line_height_percent = 200
        self._visual_update_debounce_ms = 180
        self._visual_large_document_threshold_chars = 120000
        self._visual_large_document_debounce_ms = 650
        self._source_char_count = 0
        self._text_direction_mode = "auto"
        self._rtl_ratio_threshold = 0.35
        self._zoom_steps = 0
        self._emit_timer = QTimer(self)
        self._emit_timer.setSingleShot(True)
        self._emit_timer.setInterval(110)
        self._emit_timer.timeout.connect(self._emit_serialized_source)
        self.textChanged.connect(self._schedule_source_emit)

    def configure_source_assist(
        self,
        *,
        completions: list[str] | tuple[str, ...],
        shortcuts: list[LatexShortcut] | tuple[LatexShortcut, ...],
        shortcut_min_prefix_length: int,
    ) -> None:
        self._raw_completions = list(completions)
        self._raw_shortcuts = list(shortcuts)
        self._raw_shortcut_min_prefix_length = max(
            int(shortcut_min_prefix_length),
            1,
        )

    def configure_update_debounce(
        self,
        *,
        normal_ms: int,
        large_document_threshold_chars: int,
        large_document_ms: int,
    ) -> None:
        self._visual_update_debounce_ms = max(int(normal_ms), 60)
        self._visual_large_document_threshold_chars = max(
            int(large_document_threshold_chars), 10000
        )
        self._visual_large_document_debounce_ms = max(
            int(large_document_ms), self._visual_update_debounce_ms
        )
        self._update_emit_interval()

    def configure_text_direction(
        self,
        *,
        mode: str = "auto",
        persian_ratio_threshold: float = 0.35,
    ) -> None:
        value = str(mode).strip().casefold()
        self._text_direction_mode = value if value in {"auto", "rtl", "ltr"} else "auto"
        self._rtl_ratio_threshold = max(0.05, min(float(persian_ratio_threshold), 0.95))
        self._apply_directions_to_document()

    def apply_content_padding(
        self,
        *,
        top: int = 0,
        left: int = 0,
        right: int = 0,
    ) -> None:
        """Change Visual page padding without producing a source edit."""
        was_loading = self._loading
        self._loading = True
        self._emit_timer.stop()
        document = self.document()
        was_modified = document.isModified()
        try:
            frame = document.rootFrame()
            if frame is None:
                return
            fmt = frame.frameFormat()
            fmt.setTopMargin(float(max(int(top), 0)))
            fmt.setLeftMargin(float(max(int(left), 0)))
            fmt.setRightMargin(float(max(int(right), 0)))
            frame.setFrameFormat(fmt)
            document.setModified(was_modified)
        finally:
            self._loading = was_loading
        self.viewport().update()

    def _update_emit_interval(self) -> None:
        interval = (
            self._visual_large_document_debounce_ms
            if self._source_char_count >= self._visual_large_document_threshold_chars
            else self._visual_update_debounce_ms
        )
        self._emit_timer.setInterval(int(interval))

    def apply_text_preferences(
        self,
        *,
        font_family: str,
        font_size: int,
        font_min_size: int,
        font_max_size: int,
        line_height_percent: int,
    ) -> None:
        """Apply Visual-only typography without ever editing LaTeX source.

        QTextDocument emits change notifications for character/block formatting
        as well as text edits.  Visual mode listens to ``textChanged`` so that
        genuine visual edits can be serialized back to canonical LaTeX.  If
        typography is applied while the Visual projection is still empty, an
        unguarded formatting notification can therefore serialize an empty
        document and replace a just-loaded source file.

        Settings/zoom/layout changes are presentation-only, so suppress the
        Visual-to-source timer for the whole operation.
        """
        was_loading = self._loading
        self._loading = True
        self._emit_timer.stop()
        try:
            self._configured_font_family = str(font_family).strip()
            self._configured_font_min_size = max(int(font_min_size), 1)
            self._configured_font_max_size = max(
                int(font_max_size),
                self._configured_font_min_size,
            )
            self._configured_font_size = max(
                self._configured_font_min_size,
                min(int(font_size), self._configured_font_max_size),
            )
            self._line_height_percent = max(
                60,
                min(int(line_height_percent), 300),
            )
            self._reset_font_zoom_presentation()
            self._refresh_heading_styles()
            self._apply_line_height_to_document()
        finally:
            self._loading = was_loading

    def _refresh_heading_styles(self) -> None:
        block = self.document().firstBlock()
        while block.isValid():
            data = block.userData()
            if (
                isinstance(data, _BlockMeta)
                and data.kind == "heading"
                and data.command
            ):
                self._style_heading_block(block, data.command)
            block = block.next()

    def _apply_line_height_to_document(self) -> None:
        document = self.document()
        was_modified = document.isModified()
        block = document.firstBlock()
        while block.isValid():
            cursor = QTextCursor(block)
            block_format = block.blockFormat()
            block_format.setLineHeight(
                float(self._line_height_percent),
                QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
            )
            cursor.setBlockFormat(block_format)
            block = block.next()
        document.setModified(was_modified)
        self.viewport().update()

    def reset_font_zoom(self) -> None:
        """Undo Visual zoom without generating a source edit."""
        was_loading = self._loading
        self._loading = True
        self._emit_timer.stop()
        try:
            self._reset_font_zoom_presentation()
            self._apply_line_height_to_document()
        finally:
            self._loading = was_loading

    def _reset_font_zoom_presentation(self) -> None:
        """Reset Visual font metrics; caller suppresses source serialization."""
        if self._zoom_steps > 0:
            self.zoomOut(self._zoom_steps)
        elif self._zoom_steps < 0:
            self.zoomIn(-self._zoom_steps)
        self._zoom_steps = 0

        font = self.document().defaultFont()
        if self._configured_font_family:
            font.setFamily(self._configured_font_family)
        font.setPointSize(self._configured_font_size)
        self.document().setDefaultFont(font)
        self.setFont(font)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            delta = event.angleDelta().y()
            if delta == 0:
                delta = event.pixelDelta().y()
            if delta > 0:
                self.zoomIn(1)
                self._zoom_steps += 1
            elif delta < 0:
                self.zoomOut(1)
                self._zoom_steps -= 1
            event.accept()
            return
        super().wheelEvent(event)

    @staticmethod
    def _reset_insertion_format(cursor: QTextCursor) -> None:
        """Reset character formatting before starting a new visual block.

        QTextCursor keeps the character format used by the previous insertion.
        Without an explicit reset, a raw LaTeX chip, heading, or colored span can
        leak its foreground/background/font into all following paragraphs and
        list items.  The visual editor is a projection, so every source block
        must start from the document's default character format.
        """
        cursor.setCharFormat(QTextCharFormat())

    def load_source(self, source: str, source_path: str | Path | None = None) -> None:
        """Replace the visual projection without emitting a source edit."""
        self._source_path = (
            Path(source_path).expanduser().resolve() if source_path is not None else self._source_path
        )
        self._loading = True
        self._emit_timer.stop()
        self._source_generation += 1
        self._source_char_count = len(source)
        self._update_emit_interval()
        self.clear()
        self._prefix, body, self._suffix = self._split_document(source)
        body_start_line = self._prefix.count("\n") + 1

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        blocks = self._parse_body(body, body_start_line)
        first = True
        for block in blocks:
            if not first:
                cursor.insertBlock()
                # QTextEdit continues the previous QTextList by default when
                # a new block is inserted after a list. Top-level headings or
                # paragraphs following a list must leave that list, otherwise
                # they incorrectly appear with bullets/numbers in Visual mode.
                current_list = cursor.currentList()
                if current_list is not None:
                    current_list.remove(cursor.block())
                clean_format = cursor.blockFormat()
                clean_format.setIndent(0)
                clean_format.setLeftMargin(0)
                clean_format.setRightMargin(0)
                cursor.setBlockFormat(clean_format)
            first = False
            self._reset_insertion_format(cursor)
            kind = block[0]
            if kind == "heading":
                _, command, title, raw_heading, source_line = block
                self._insert_heading(
                    cursor,
                    command,
                    title,
                    raw_heading,
                    source_line=source_line,
                )
            elif kind == "list":
                _, entries = block
                self._insert_list_entries(cursor, entries)
            elif kind == "graphic":
                _, raw, graphic_path, source_line = block
                self._insert_graphic_block(
                    cursor, raw, graphic_path, source_line=source_line
                )
            elif kind == "raw":
                _, raw, source_line = block
                self._insert_raw_block(cursor, raw, source_line=source_line)
            elif kind == "blank":
                _, source_line = block
                cursor.block().setUserData(
                    _BlockMeta(kind="blank", source_line=source_line)
                )
            else:
                _, text, source_line, source_segments = block
                cursor.block().setUserData(
                    _BlockMeta(
                        kind="paragraph",
                        source_line=source_line,
                        source_segments=source_segments,
                    )
                )
                self._insert_inline_latex(cursor, text)

        self.moveCursor(QTextCursor.MoveOperation.Start)
        self._apply_line_height_to_document()
        self._apply_directions_to_document()
        self.document().setModified(False)
        self._has_loaded_source = True
        self._emit_timer.stop()
        self._loading = False

    def go_to_source_location(
        self,
        line_number: int,
        column: int = 1,
        align_top: bool = True,
    ) -> None:
        """Move Visual cursor to the block corresponding to a source location."""
        target_line = max(int(line_number), 1)
        target_column = max(int(column), 1)
        best_block = None
        best_line = -1

        block = self.document().firstBlock()
        while block.isValid():
            data = block.userData()
            meta = data if isinstance(data, _BlockMeta) else None
            if meta is not None and meta.source_line > 0:
                if meta.source_line <= target_line and meta.source_line >= best_line:
                    best_block = block
                    best_line = meta.source_line
                if meta.source_segments:
                    segment_lines = [line for line, _text in meta.source_segments]
                    if target_line in segment_lines:
                        best_block = block
                        best_line = target_line
                        break
            block = block.next()

        if best_block is None:
            best_block = self.document().firstBlock()
        if not best_block.isValid():
            return

        offset = self._visual_offset_for_source_location(
            best_block,
            target_line,
            target_column,
        )
        cursor = QTextCursor(best_block)
        cursor.setPosition(
            best_block.position() + max(0, min(offset, len(best_block.text())))
        )
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        if align_top:
            rectangle = self.cursorRect(cursor)
            scrollbar = self.verticalScrollBar()
            scrollbar.setValue(scrollbar.value() + rectangle.top())
        self.setFocus()

    def current_source_location(self) -> tuple[int, int]:
        """Return the canonical source location represented by Visual cursor."""
        return self.source_location_for_position(self.textCursor().position())

    def source_location_for_position(self, position: int) -> tuple[int, int]:
        """Map an absolute Visual position to an approximate source line/column."""
        maximum = max(self.document().characterCount() - 1, 0)
        position = max(0, min(int(position), maximum))
        block = self.document().findBlock(position)
        meta = self._source_meta_for_block(block)
        if meta is None:
            return 1, 1
        source_line = max(meta.source_line, 1)
        if not meta.source_segments:
            return source_line, max(position - block.position() + 1, 1)
        visual_offset = max(position - block.position(), 0)
        consumed = 0
        for index, (line_number, source_text) in enumerate(meta.source_segments):
            display = self._mapping_display_text(source_text)
            segment_end = consumed + len(display)
            if visual_offset <= segment_end or index == len(meta.source_segments) - 1:
                return (
                    max(int(line_number), 1),
                    max(visual_offset - consumed + 1, 1),
                )
            consumed = segment_end + 1
        return source_line, 1

    def visual_position_for_source_location(self, line_number: int, column: int = 1) -> int:
        target_line = max(int(line_number), 1)
        target_column = max(int(column), 1)
        best_block = None
        best_line = -1
        block = self.document().firstBlock()
        while block.isValid():
            data = block.userData()
            meta = data if isinstance(data, _BlockMeta) else None
            if meta is not None and meta.source_line > 0:
                if meta.source_line <= target_line and meta.source_line >= best_line:
                    best_block = block
                    best_line = meta.source_line
                if meta.source_segments and target_line in [x[0] for x in meta.source_segments]:
                    best_block = block
                    break
            block = block.next()
        if best_block is None or not best_block.isValid():
            return 0
        offset = self._visual_offset_for_source_location(
            best_block, target_line, target_column
        )
        return best_block.position() + max(0, min(offset, len(best_block.text())))

    def source_selection_locations(self) -> tuple[tuple[int, int], tuple[int, int]]:
        cursor = self.textCursor()
        return (
            self.source_location_for_position(cursor.anchor()),
            self.source_location_for_position(cursor.position()),
        )

    def set_selection_from_source_locations(
        self,
        anchor: tuple[int, int],
        position: tuple[int, int],
        *,
        ensure_visible: bool = True,
    ) -> None:
        anchor_pos = self.visual_position_for_source_location(*anchor)
        position_pos = self.visual_position_for_source_location(*position)
        cursor = QTextCursor(self.document())
        cursor.setPosition(anchor_pos)
        cursor.setPosition(position_pos, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        if ensure_visible:
            self.ensureCursorVisible()

    def first_visible_source_position(self) -> tuple[int, int]:
        cursor = self.cursorForPosition(QPoint(4, 4))
        return self.source_location_for_position(cursor.position())

    def source_location_at_view_y(self, y: int) -> tuple[int, int]:
        cursor = self.cursorForPosition(
            QPoint(max(24, self.viewport().width() // 2), int(y))
        )
        return self.source_location_for_position(cursor.position())

    def marker_y_for_source_location(
        self, line_number: int, column: int = 1
    ) -> float | None:
        position = self.visual_position_for_source_location(line_number, column)
        if position < 0:
            return None
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        rect = self.cursorRect(cursor)
        return float(rect.center().y())

    @staticmethod
    def _source_meta_for_block(block) -> _BlockMeta | None:
        current = block
        while current.isValid():
            data = current.userData()
            if isinstance(data, _BlockMeta) and data.source_line > 0:
                return data
            current = current.previous()
        return None

    def _visual_offset_for_source_location(
        self,
        block,
        line_number: int,
        column: int,
    ) -> int:
        data = block.userData()
        meta = data if isinstance(data, _BlockMeta) else None
        if meta is None or not meta.source_segments:
            return 0

        consumed = 0
        for segment_line, source_text in meta.source_segments:
            display = self._mapping_display_text(source_text)
            if int(segment_line) == int(line_number):
                return consumed + min(max(int(column) - 1, 0), len(display))
            if int(segment_line) < int(line_number):
                consumed += len(display) + 1
            else:
                break
        return min(consumed, len(block.text()))

    def _mapping_display_text(self, text: str) -> str:
        """Produce the visible inline text used for source/Visual cursor mapping."""
        position = 0
        parts: list[str] = []
        while position < len(text):
            parsed = self._match_known_inline(text, position)
            if parsed is not None:
                end, inner, _fmt = parsed
                parts.append(self._mapping_display_text(inner))
                position = end
                continue

            raw = self._match_raw_inline(text, position)
            if raw is not None:
                end, raw_text = raw
                parts.append(self._visual_raw_inline_text(raw_text))
                position = end
                continue

            next_special = self._next_inline_special(text, position + 1)
            parts.append(self._unescape_plain_text(text[position:next_special]))
            position = next_special
        return "".join(parts)

    def serialized_source(self) -> str:
        body_lines: list[str] = []
        block = self.document().firstBlock()
        list_stack: list[str] = []

        def close_lists(target_depth: int = 0) -> None:
            while len(list_stack) > target_depth:
                environment = list_stack.pop()
                body_lines.append(
                    "    " * len(list_stack)
                    + f"\\end{{{environment}}}"
                )

        def open_list(environment: str) -> None:
            body_lines.append(
                "    " * len(list_stack)
                + f"\\begin{{{environment}}}"
            )
            list_stack.append(environment)

        while block.isValid():
            data = block.userData()
            meta = data if isinstance(data, _BlockMeta) else _BlockMeta()
            text_list = block.textList()

            if text_list is not None or meta.kind == "list_item":
                fmt = text_list.format() if text_list is not None else None
                inferred_kind = "itemize"
                if fmt is not None and fmt.style() in {
                    QTextListFormat.Style.ListDecimal,
                    QTextListFormat.Style.ListLowerAlpha,
                    QTextListFormat.Style.ListUpperAlpha,
                    QTextListFormat.Style.ListLowerRoman,
                    QTextListFormat.Style.ListUpperRoman,
                }:
                    inferred_kind = "enumerate"

                list_kind = (
                    meta.command
                    if meta.command in {"itemize", "enumerate"}
                    else inferred_kind
                )
                depth = meta.depth
                if depth <= 0 and fmt is not None:
                    depth = max(int(fmt.indent()), 1)
                depth = max(depth, 1)

                # A visual QTextList can occasionally report an indentation
                # jump after interactive edits. Keep emitted LaTeX balanced by
                # growing one nesting level at a time.
                depth = min(depth, len(list_stack) + 1)

                close_lists(depth)
                if len(list_stack) == depth and list_stack:
                    if list_stack[-1] != list_kind:
                        close_lists(depth - 1)

                while len(list_stack) < depth:
                    open_list(list_kind)

                if meta.raw:
                    for directive in meta.raw.splitlines():
                        if directive.strip():
                            body_lines.append(
                                "    " * len(list_stack) + directive.strip()
                            )

                body_lines.append(
                    "    " * len(list_stack)
                    + "\\item "
                    + self._serialize_inline_block(block)
                )
                block = block.next()
                continue

            close_lists(0)

            if meta.kind == "heading" and meta.command:
                serialized_title = self._serialize_inline_block(block)
                if meta.raw and serialized_title == meta.display:
                    body_lines.append(meta.raw)
                else:
                    labels = ""
                    if meta.raw:
                        labels = "".join(
                            re.findall(r"\\label\s*\{[^}]*\}", meta.raw)
                        )
                    body_lines.append(
                        f"\\{meta.command}{{{serialized_title}}}{labels}"
                    )
            elif meta.kind == "graphic":
                body_lines.append(meta.raw)
            elif meta.kind == "raw":
                body_lines.append(meta.raw)
            elif meta.kind == "blank":
                body_lines.append("")
            else:
                body_lines.append(self._serialize_inline_block(block))
            block = block.next()

        close_lists(0)
        body = "\n".join(body_lines).strip("\n")

        if self._prefix:
            prefix = self._prefix.rstrip()
            suffix = self._suffix.lstrip()
            if body:
                return f"{prefix}\n\n{body}\n\n{suffix}"
            return f"{prefix}\n{suffix}"
        return body

    def toggle_bold(self) -> None:
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        is_bold = cursor.charFormat().fontWeight() >= QFont.Weight.Bold
        fmt.setFontWeight(QFont.Weight.Normal if is_bold else QFont.Weight.Bold)
        self._merge_selection_format(fmt)

    def toggle_italic(self) -> None:
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        fmt.setFontItalic(not cursor.charFormat().fontItalic())
        self._merge_selection_format(fmt)

    def set_text_color(self, latex_color: str, css_color: str | None = None) -> None:
        fmt = QTextCharFormat()
        fmt.setProperty(_LATEX_TEXT_COLOR_PROPERTY, str(latex_color))
        color = css_color or self._LATEX_TO_QCOLOR.get(str(latex_color), "#101828")
        fmt.setForeground(QColor(color))
        self._merge_selection_format(fmt)

    def set_highlight(self, latex_color: str, css_color: str | None = None) -> None:
        fmt = QTextCharFormat()
        fmt.setProperty(_LATEX_HIGHLIGHT_PROPERTY, str(latex_color))
        color = css_color or self._HIGHLIGHT_TO_QCOLOR.get(
            str(latex_color), "#fff6bf"
        )
        fmt.setBackground(QColor(color))
        self._merge_selection_format(fmt)

    def set_heading(self, command: str) -> None:
        command = str(command).strip().lower()
        if command not in self._HEADING_COMMANDS:
            return
        cursor = self.textCursor()
        cursor.beginEditBlock()
        start = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        end = cursor.selectionEnd() if cursor.hasSelection() else cursor.position()
        start_block = self.document().findBlock(start)
        end_block = self.document().findBlock(end)
        block = start_block
        while block.isValid():
            block.setUserData(_BlockMeta(kind="heading", command=command))
            self._style_heading_block(block, command)
            if block == end_block:
                break
            block = block.next()
        cursor.endEditBlock()
        self.viewport().update()
        self._schedule_source_emit()

    def set_list(self, kind: str) -> None:
        kind = "enumerate" if str(kind) == "enumerate" else "itemize"
        cursor = self.textCursor()
        style = (
            QTextListFormat.Style.ListDecimal
            if kind == "enumerate"
            else QTextListFormat.Style.ListDisc
        )
        fmt = QTextListFormat()
        fmt.setStyle(style)
        fmt.setIndent(1)
        cursor.createList(fmt)
        self._schedule_source_emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Prevent visual-only formatting from leaking into source semantics.

        Visual headings are deliberately drawn bold and large, but that style
        is *structural UI decoration*, not an implicit ``\textbf`` command.
        Likewise, an inline raw-LaTeX token such as ``$\alpha$`` carries a
        private round-trip property.  QTextEdit normally inherits both kinds
        of character formatting when the user continues typing.  We detach
        those private properties before ordinary text insertion and reset a
        newly-created paragraph after Enter so typing below a heading starts as
        normal prose instead of silently becoming bold LaTeX.
        """
        key = event.key()
        modifiers = event.modifiers()
        control = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        alt_or_meta = bool(
            modifiers
            & (
                Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )
        if control and not alt_or_meta:
            if key == Qt.Key.Key_Z:
                if modifiers & Qt.KeyboardModifier.ShiftModifier:
                    self.redo()
                else:
                    self.undo()
                event.accept()
                return
            if (
                key == Qt.Key.Key_Y
                and not bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
            ):
                self.redo()
                event.accept()
                return

        text = event.text()
        cursor_before = self.textCursor()
        data_before = cursor_before.block().userData()
        was_heading = isinstance(data_before, _BlockMeta) and data_before.kind == "heading"

        text_insertion = bool(text) and key not in {
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
        }
        if text_insertion and not cursor_before.hasSelection():
            self._detach_insertion_format_from_private_visual_state()

        super().keyPressEvent(event)

        if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self._normalize_new_block_after_enter(was_heading=was_heading)

    def _normalize_new_block_after_enter(self, *, was_heading: bool) -> None:
        cursor = self.textCursor()
        block = cursor.block()
        text_list = block.textList()

        # Keep list continuation semantics, but never continue inline bold,
        # italic, highlight, raw-token or visual-heading character formatting.
        clean = QTextCharFormat()
        clean.setFontFamily(self.font().family())
        clean.setFontPointSize(self.font().pointSizeF())
        self.setCurrentCharFormat(clean)

        if text_list is not None:
            return

        if was_heading or not isinstance(block.userData(), _BlockMeta):
            block.setUserData(_BlockMeta(kind="paragraph"))

        block_format = block.blockFormat()
        block_format.setIndent(0)
        block_format.setLeftMargin(0)
        block_format.setRightMargin(0)
        block_format.setTopMargin(0)
        block_format.setBottomMargin(0)
        block_format.setLineHeight(
            float(self._line_height_percent),
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )
        cursor.setBlockFormat(block_format)
        self._apply_direction_to_block(block)

    def _detach_insertion_format_from_private_visual_state(self) -> None:
        current = QTextCharFormat(self.currentCharFormat())
        changed = False
        if current.property(_RAW_LATEX_PROPERTY):
            current.clearProperty(_RAW_LATEX_PROPERTY)
            current.clearBackground()
            current.clearForeground()
            current.setFontFamily(self.font().family())
            changed = True
        if current.property(_VISUAL_HEADING_PROPERTY):
            current.clearProperty(_VISUAL_HEADING_PROPERTY)
            current.setFontWeight(QFont.Weight.Normal)
            current.setFontPointSize(self.font().pointSizeF())
            changed = True
        if changed:
            self.setCurrentCharFormat(current)

    def insertFromMimeData(self, source) -> None:
        if not self.textCursor().hasSelection():
            self._detach_insertion_format_from_private_visual_state()
        super().insertFromMimeData(source)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self.createStandardContextMenu()
        menu.addSeparator()

        click_cursor = self.cursorForPosition(event.pos())
        click_meta = click_cursor.block().userData()
        is_existing_graphic = (
            isinstance(click_meta, _BlockMeta)
            and click_meta.kind == "graphic"
        )
        graphic_action = menu.addAction(
            "Edit image in iPad…"
            if is_existing_graphic
            else "Insert image in iPad…"
        )

        cursor = self.textCursor()
        update_action = None
        if cursor.hasSelection():
            update_action = menu.addAction("Update selected LaTeX source…")

        insert_action = menu.addAction("Insert raw LaTeX here…")
        chosen = menu.exec(event.globalPos())
        if chosen == graphic_action:
            if not cursor.hasSelection():
                self.setTextCursor(click_cursor)
            line, column = self.current_source_location()
            self.graphic_requested.emit(line, column)
        elif update_action is not None and chosen == update_action:
            self._edit_selected_latex_source()
        elif chosen == insert_action:
            self._edit_raw_latex_at_cursor()

    def _open_raw_latex_dialog(
        self,
        *,
        title: str,
        initial_text: str,
        instruction: str,
    ) -> str | None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(720, 460)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(instruction, dialog))
        editor = RawLatexSnippetEditor(
            completions=self._raw_completions,
            shortcuts=self._raw_shortcuts,
            shortcut_min_prefix_length=self._raw_shortcut_min_prefix_length,
            parent=dialog,
        )
        editor.setPlainText(initial_text)
        layout.addWidget(editor, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        editor.setFocus()
        editor.moveCursor(QTextCursor.MoveOperation.End)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return editor.toPlainText().strip("\n")

    def _edit_raw_latex_at_cursor(self) -> None:
        cursor = self.textCursor()
        block = cursor.block()
        data = block.userData()
        existing = data.raw if isinstance(data, _BlockMeta) and data.kind == "raw" else ""
        raw = self._open_raw_latex_dialog(
            title="Raw LaTeX",
            initial_text=existing,
            instruction=(
                "Write LaTeX for this position. This mini source editor "
                "supports LaTeX command completion and latex_shortcuts.yaml "
                "expansions (for example, type 'lis'). Press OK to insert it "
                "into the canonical source."
            ),
        )
        if raw is None or not raw:
            return

        if isinstance(data, _BlockMeta) and data.kind == "raw":
            data.raw = raw
            data.display = self._raw_display(raw)
            replacement = QTextCursor(block)
            replacement.select(QTextCursor.SelectionType.BlockUnderCursor)
            replacement.removeSelectedText()
            replacement.insertText(data.display, self._raw_char_format())
            block.setUserData(data)
        else:
            cursor.beginEditBlock()
            if cursor.positionInBlock() != 0 or block.text().strip():
                cursor.insertBlock()
            self._insert_raw_block(cursor, raw)
            cursor.insertBlock()
            cursor.endEditBlock()
        self._emit_source_and_reproject()

    def _edit_selected_latex_source(self) -> None:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return

        initial = self._selected_latex_source(cursor)
        raw = self._open_raw_latex_dialog(
            title="Update selected LaTeX source",
            initial_text=initial,
            instruction=(
                "This is the LaTeX represented by the selected Visual text. "
                "Edit it freely, then press OK. Source, Visual, Structure and "
                "Preview will be updated from the edited LaTeX."
            ),
        )
        if raw is None:
            return

        self._replace_selection_with_latex(cursor, raw)

    def _selected_latex_source(self, cursor: QTextCursor) -> str:
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        if end <= start:
            return ""

        document = self.document()
        first = document.findBlock(start)
        last = document.findBlock(max(start, end - 1))
        if not first.isValid():
            return cursor.selectedText().replace("\u2029", "\n")

        if first == last:
            return self._serialize_inline_range(first, start, end)

        lines: list[str] = []
        list_stack: list[str] = []

        def close_lists(target_depth: int = 0) -> None:
            while len(list_stack) > target_depth:
                environment = list_stack.pop()
                lines.append("    " * len(list_stack) + f"\\end{{{environment}}}")

        block = first
        while block.isValid():
            block_start = block.position()
            block_end = block_start + len(block.text())
            selected_start = max(start, block_start)
            selected_end = min(end, block_end)
            meta_data = block.userData()
            meta = meta_data if isinstance(meta_data, _BlockMeta) else _BlockMeta()
            inline = self._serialize_inline_range(block, selected_start, selected_end)

            if meta.kind == "list_item" or block.textList() is not None:
                depth = max(meta.depth, 1)
                environment = meta.command if meta.command in {"itemize", "enumerate"} else "itemize"
                while len(list_stack) > depth:
                    close_lists(depth)
                if len(list_stack) == depth and list_stack and list_stack[-1] != environment:
                    close_lists(depth - 1)
                while len(list_stack) < depth:
                    lines.append("    " * len(list_stack) + f"\\begin{{{environment}}}")
                    list_stack.append(environment)
                if meta.raw:
                    for directive in meta.raw.splitlines():
                        if directive.strip():
                            lines.append(
                                "    " * len(list_stack) + directive.strip()
                            )
                lines.append("    " * len(list_stack) + "\\item " + inline)
            else:
                close_lists(0)
                whole_block = selected_start <= block_start and selected_end >= block_end
                if meta.kind == "heading" and meta.command and whole_block:
                    lines.append(f"\\{meta.command}{{{inline}}}")
                elif meta.kind == "raw":
                    lines.append(meta.raw)
                else:
                    lines.append(inline)

            if block == last:
                break
            block = block.next()

        close_lists(0)
        return "\n".join(lines).strip("\n")

    def _serialize_inline_range(self, block, start: int, end: int) -> str:
        if end <= start:
            return ""
        parts: list[str] = []
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if not fragment.isValid():
                iterator += 1
                continue
            fragment_start = fragment.position()
            fragment_end = fragment_start + len(fragment.text())
            overlap_start = max(start, fragment_start)
            overlap_end = min(end, fragment_end)
            if overlap_end <= overlap_start:
                iterator += 1
                continue

            fmt = fragment.charFormat()
            raw = fmt.property(_RAW_LATEX_PROPERTY)
            if raw:
                # A displayed token such as α may represent a longer source
                # sequence such as ``$\\alpha$``. Any selection touching the
                # token therefore exposes the complete underlying LaTeX.
                parts.append(str(raw))
                iterator += 1
                continue

            offset_start = overlap_start - fragment_start
            offset_end = overlap_end - fragment_start
            text = self._escape_plain_text(fragment.text()[offset_start:offset_end])
            if not text:
                iterator += 1
                continue
            if (
                fmt.fontWeight() >= QFont.Weight.Bold
                and not bool(fmt.property(_VISUAL_HEADING_PROPERTY))
            ):
                text = f"\\textbf{{{text}}}"
            if fmt.fontItalic():
                text = f"\\textit{{{text}}}"
            latex_color = fmt.property(_LATEX_TEXT_COLOR_PROPERTY)
            if latex_color:
                text = f"\\textcolor{{{latex_color}}}{{{text}}}"
            highlight = fmt.property(_LATEX_HIGHLIGHT_PROPERTY)
            if highlight:
                text = f"\\colorbox{{{highlight}}}{{{text}}}"
            parts.append(text)
            iterator += 1
        return "".join(parts)

    @staticmethod
    def _looks_block_level_latex(raw: str) -> bool:
        if "\n" in raw:
            return True
        return bool(
            re.search(
                r"\\(?:begin|end|part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\\b",
                raw,
            )
        )

    def _replace_selection_with_latex(self, cursor: QTextCursor, raw: str) -> None:
        start_block = self.document().findBlock(cursor.selectionStart())
        end_block = self.document().findBlock(max(cursor.selectionStart(), cursor.selectionEnd() - 1))
        inline_safe = start_block == end_block and not self._looks_block_level_latex(raw)

        cursor.beginEditBlock()
        cursor.removeSelectedText()
        if inline_safe:
            self._reset_insertion_format(cursor)
            self._insert_inline_latex(cursor, raw)
        else:
            current_block = cursor.block()
            if cursor.positionInBlock() != 0 or current_block.text().strip():
                cursor.insertBlock()
            self._insert_raw_block(cursor, raw)
            cursor.insertBlock()
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self._emit_source_and_reproject(reproject=not inline_safe)

    def _emit_source_and_reproject(self, *, reproject: bool = True) -> None:
        if self._loading:
            return
        self._emit_timer.stop()
        source = self.serialized_source()
        self.source_changed.emit(source)
        if reproject:
            # Reparse edited raw code so supported constructs immediately turn
            # back into their graphical representation instead of remaining a
            # grey raw-code block.
            QTimer.singleShot(0, lambda value=source: self.load_source(value))

    def _merge_selection_format(self, fmt: QTextCharFormat) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            self.mergeCurrentCharFormat(fmt)
        self.setTextCursor(cursor)
        self.setFocus()
        self._schedule_source_emit()

    def _schedule_source_emit(self) -> None:
        if self._loading or not self._has_loaded_source:
            return
        self._apply_direction_to_block(self.textCursor().block())
        self._update_emit_interval()
        self._emit_timer.start()

    def _emit_serialized_source(self) -> None:
        if self._loading or not self._has_loaded_source:
            return
        source = self.serialized_source()
        self._source_char_count = len(source)
        self._update_emit_interval()
        self.source_changed.emit(source)

    @staticmethod
    def _strong_script_counts(text: str) -> tuple[int, int]:
        rtl = 0
        latin = 0
        for char in str(text):
            code = ord(char)
            if (
                0x0590 <= code <= 0x08FF
                or 0xFB1D <= code <= 0xFDFF
                or 0xFE70 <= code <= 0xFEFF
            ):
                if char.isalpha():
                    rtl += 1
            elif ("A" <= char <= "Z") or ("a" <= char <= "z"):
                latin += 1
        return rtl, latin

    def _block_should_be_rtl(self, block) -> bool:
        data = block.userData()
        if isinstance(data, _BlockMeta) and data.kind == "raw":
            return False
        mode = self._text_direction_mode
        if mode == "ltr":
            return False
        if mode == "rtl":
            return True
        rtl, latin = self._strong_script_counts(block.text())
        total = rtl + latin
        return rtl > 0 and (total == 0 or (rtl / max(total, 1)) >= self._rtl_ratio_threshold)

    def _apply_direction_to_block(self, block) -> None:
        if not block.isValid():
            return
        document = self.document()
        was_modified = document.isModified()
        was_loading = self._loading
        self._loading = True
        try:
            cursor = QTextCursor(block)
            fmt = block.blockFormat()
            rtl = self._block_should_be_rtl(block)
            fmt.setLayoutDirection(
                Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight
            )
            fmt.setAlignment(
                (Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft)
                | Qt.AlignmentFlag.AlignAbsolute
            )
            cursor.setBlockFormat(fmt)
            document.setModified(was_modified)
        finally:
            self._loading = was_loading

    def _apply_directions_to_document(self) -> None:
        was_loading = self._loading
        self._loading = True
        self._emit_timer.stop()
        try:
            block = self.document().firstBlock()
            while block.isValid():
                self._apply_direction_to_block(block)
                block = block.next()
        finally:
            self._loading = was_loading
        self.viewport().update()

    @classmethod
    def _split_document(cls, source: str) -> tuple[str, str, str]:
        begin = re.search(r"\\begin\s*\{document\}", source)
        if begin is None:
            return "", source, ""
        end_matches = list(re.finditer(r"\\end\s*\{document\}", source))
        if not end_matches:
            return "", source, ""
        end = end_matches[-1]
        if end.start() < begin.end():
            return "", source, ""
        return source[: begin.end()], source[begin.end() : end.start()], source[end.start() :]

    @classmethod
    def _parse_body(
        cls,
        body: str,
        base_line: int = 1,
    ) -> list[tuple]:
        """Parse Visual blocks while preserving their source line anchors."""
        lines = body.splitlines()
        result: list[tuple] = []
        index = 0

        def source_line(line_index: int) -> int:
            return max(int(base_line) + int(line_index), 1)

        while index < len(lines):
            line = lines[index]
            line_number = source_line(index)
            stripped = line.strip()
            if not stripped:
                result.append(("blank", line_number))
                index += 1
                continue

            heading = cls._parse_heading_line(line)
            if heading is not None:
                command, title, raw_heading = heading
                result.append(
                    ("heading", command, title, raw_heading, line_number)
                )
                index += 1
                continue

            begin_list = re.match(r"^\s*\\begin\{(itemize|enumerate)\}\s*$", line)
            if begin_list:
                start_index = index
                entries: list[tuple[int, str, str, str, int]] = []
                stack: list[str] = []
                pending_directives: dict[int, list[str]] = {}
                current_entry = -1
                malformed = False

                while index < len(lines):
                    candidate = lines[index]
                    candidate_line = source_line(index)
                    candidate_stripped = candidate.strip()
                    begin_match = re.match(
                        r"^\s*\\begin\{(itemize|enumerate)\}\s*$",
                        candidate,
                    )
                    if begin_match:
                        stack.append(begin_match.group(1))
                        index += 1
                        continue

                    end_match = re.match(
                        r"^\s*\\end\{(itemize|enumerate)\}\s*$",
                        candidate,
                    )
                    if end_match:
                        if not stack or stack[-1] != end_match.group(1):
                            malformed = True
                            index += 1
                            break
                        stack.pop()
                        index += 1
                        if not stack:
                            break
                        continue

                    if candidate_stripped == r"\tightlist" and stack:
                        pending_directives.setdefault(len(stack), []).append(
                            candidate_stripped
                        )
                        index += 1
                        continue

                    item_match = re.match(r"^\s*\\item(?:\s+|$)(.*)$", candidate)
                    if item_match and stack:
                        entries.append(
                            (
                                len(stack),
                                stack[-1],
                                item_match.group(1).strip(),
                                "\n".join(
                                    pending_directives.pop(len(stack), [])
                                ),
                                candidate_line,
                            )
                        )
                        current_entry = len(entries) - 1
                        index += 1
                        continue

                    # Blank lines inside a list only provide source spacing.
                    # Ordinary continuation lines belong to the current item.
                    if not candidate_stripped:
                        index += 1
                        continue
                    if stack and current_entry >= 0:
                        depth, environment, text, directives, item_line = entries[current_entry]
                        separator = " " if text else ""
                        entries[current_entry] = (
                            depth,
                            environment,
                            text + separator + candidate_stripped,
                            directives,
                            item_line,
                        )
                        index += 1
                        continue

                    malformed = True
                    index += 1
                    break

                if malformed or stack:
                    result.append(
                        (
                            "raw",
                            "\n".join(lines[start_index:index]),
                            source_line(start_index),
                        )
                    )
                else:
                    result.append(("list", entries))
                continue

            # A normal Mind Mirror image is stored as a full figure block in
            # Source mode, but Visual mode should show the image itself rather
            # than raw \begin{figure}/\end{figure} commands. Preserve the
            # complete raw block in metadata so switching modes is lossless.
            figure_begin = re.match(r"^\s*\\begin\{figure\}(?:\s*\[[^\]]*\])?\s*$", line)
            if figure_begin:
                raw_lines = [line]
                start_line = line_number
                figure_index = index + 1
                depth = 1
                while figure_index < len(lines) and depth > 0:
                    candidate = lines[figure_index]
                    if re.search(r"\\begin\{figure\}", candidate):
                        depth += 1
                    if re.search(r"\\end\{figure\}", candidate):
                        depth -= 1
                    raw_lines.append(candidate)
                    figure_index += 1
                raw_figure = "\n".join(raw_lines)
                graphic_inside = re.search(
                    r"\\includegraphics(?:\s*\[[^\]]*\])?\s*\{([^}]+)\}",
                    raw_figure,
                    re.MULTILINE,
                )
                if depth == 0 and graphic_inside:
                    result.append((
                        "graphic",
                        raw_figure,
                        graphic_inside.group(1).strip(),
                        start_line,
                    ))
                    index = figure_index
                    continue

            graphic_match = re.match(
                r"^\s*(\\includegraphics(?:\s*\[[^\]]*\])?\s*\{([^}]+)\})\s*$",
                line,
            )
            if graphic_match:
                result.append(("graphic", graphic_match.group(1), graphic_match.group(2).strip(), line_number))
                index += 1
                continue

            begin_env = re.match(r"^\s*\\begin\{([^}]+)\}", line)
            if begin_env:
                environment = begin_env.group(1)
                raw_lines = [line]
                depth = 1
                start_line = line_number
                index += 1
                while index < len(lines) and depth > 0:
                    candidate = lines[index]
                    if re.search(rf"\\begin\{{{re.escape(environment)}\}}", candidate):
                        depth += 1
                    if re.search(rf"\\end\{{{re.escape(environment)}\}}", candidate):
                        depth -= 1
                    raw_lines.append(candidate)
                    index += 1
                result.append(("raw", "\n".join(raw_lines), start_line))
                continue

            if stripped.startswith("%"):
                result.append(("raw", line, line_number))
                index += 1
                continue

            if stripped.startswith("\\") and not cls._starts_with_inline_construct(stripped):
                result.append(("raw", line, line_number))
                index += 1
                continue

            paragraph_start = index
            paragraph: list[str] = []
            source_segments: list[tuple[int, str]] = []
            while index < len(lines):
                candidate = lines[index]
                candidate_stripped = candidate.strip()
                if (
                    not candidate_stripped
                    or candidate.lstrip().startswith("\\")
                    or candidate.lstrip().startswith("%")
                ):
                    break
                paragraph.append(candidate_stripped)
                source_segments.append((source_line(index), candidate_stripped))
                index += 1

            # Inline LaTeX at the beginning of a paragraph is accepted by the
            # parser, so make sure the first line is consumed even when the
            # loop above did not run for an unusual construct.
            if not paragraph:
                paragraph.append(line.strip())
                source_segments.append((line_number, line.strip()))
                index = max(index, paragraph_start + 1)

            result.append(
                (
                    "paragraph",
                    " ".join(paragraph),
                    source_line(paragraph_start),
                    source_segments,
                )
            )

        # Collapse repeated blank visual blocks while keeping paragraph gaps.
        collapsed: list[tuple] = []
        for item in result:
            if item[0] == "blank" and collapsed and collapsed[-1][0] == "blank":
                continue
            collapsed.append(item)
        return collapsed

    @classmethod
    def _parse_heading_line(cls, line: str) -> tuple[str, str, str] | None:
        """Parse sectioning commands with nested arguments and trailing labels.

        Pandoc-style Persian headings commonly contain ``\\texorpdfstring`` and
        ``\\hypertarget`` inside the mandatory argument.  A regular expression
        that stops at the first closing brace treats those headings as raw code.
        This parser follows balanced braces and keeps the original command for
        lossless round-tripping when only another part of the Visual document is
        edited.
        """
        stripped = line.strip()
        match = re.match(
            r"\\(" + "|".join(cls._HEADING_COMMANDS) + r")\*?",
            stripped,
        )
        if match is None:
            return None
        command = match.group(1)
        position = match.end()
        while position < len(stripped) and stripped[position].isspace():
            position += 1

        if position < len(stripped) and stripped[position] == "[":
            position = cls._skip_balanced(stripped, position, "[", "]")
            if position < 0:
                return None
            while position < len(stripped) and stripped[position].isspace():
                position += 1

        if position >= len(stripped) or stripped[position] != "{":
            return None
        title_source, after = cls._read_braced(stripped, position)
        if after is None:
            return None
        trailing = stripped[after:].strip()
        if trailing and not re.fullmatch(
            r"(?:\\label\s*\{[^}]*\}\s*)+",
            trailing,
        ):
            return None
        return command, cls._heading_display_title(title_source), stripped

    @staticmethod
    def _skip_balanced(text: str, start: int, opener: str, closer: str) -> int:
        depth = 0
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return index + 1
        return -1

    @classmethod
    def _heading_display_title(cls, source: str) -> str:
        value = source.strip()
        if value.startswith(r"\texorpdfstring"):
            position = len(r"\texorpdfstring")
            if position < len(value) and value[position] == "{":
                _first, after_first = cls._read_braced(value, position)
                if (
                    after_first is not None
                    and after_first < len(value)
                    and value[after_first] == "{"
                ):
                    second, after_second = cls._read_braced(value, after_first)
                    if after_second is not None:
                        return cls._plain_heading_text(second)
        return cls._plain_heading_text(value)

    @staticmethod
    def _plain_heading_text(source: str) -> str:
        value = re.sub(
            r"\\protect\s*\\hypertarget\s*\{[^}]*\}\s*\{[^}]*\}",
            "",
            source,
        )
        value = re.sub(r"\\label\s*\{[^}]*\}", "", value)
        return value.strip()

    @staticmethod
    def _starts_with_inline_construct(stripped: str) -> bool:
        return bool(
            stripped.startswith((
                r"\textbf{",
                r"\textit{",
                r"\emph{",
                r"\textcolor{",
                r"\colorbox{",
                "$",
                r"\(",
            ))
        )

    def _insert_heading(
        self,
        cursor: QTextCursor,
        command: str,
        title: str,
        raw_heading: str = "",
        source_line: int = 0,
    ) -> None:
        cursor.block().setUserData(
            _BlockMeta(
                kind="heading",
                command=command,
                raw=raw_heading,
                display=title,
                source_line=source_line,
            )
        )
        self._insert_inline_latex(cursor, title)
        self._style_heading_block(cursor.block(), command)

    def _style_heading_block(self, block, command: str) -> None:
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold)
        heading_base = float(self._HEADING_SIZES.get(command, 16))
        fmt.setFontPointSize(
            heading_base * (float(self._configured_font_size) / 16.0)
        )
        # Mark this bold/size as visual structure only. Serialization must not
        # turn the editor's heading appearance into ``\textbf{...}``.
        fmt.setProperty(_VISUAL_HEADING_PROPERTY, True)
        cursor.mergeCharFormat(fmt)
        block_format = block.blockFormat()
        block_format.setTopMargin(12)
        block_format.setBottomMargin(6)
        cursor.setBlockFormat(block_format)

    def _insert_list_entries(
        self,
        cursor: QTextCursor,
        entries: list[tuple],
    ) -> None:
        if not entries:
            entries = [(1, "itemize", "", "")]

        for item_index, entry in enumerate(entries):
            if len(entry) >= 5:
                depth, kind, item, directives, source_line = entry[:5]
            elif len(entry) >= 4:
                depth, kind, item, directives = entry[:4]
                source_line = 0
            else:
                depth, kind, item = entry[:3]
                directives = ""
                source_line = 0
            depth = max(int(depth), 1)
            kind = "enumerate" if kind == "enumerate" else "itemize"
            if item_index > 0:
                cursor.insertBlock()

            style = QTextListFormat.Style.ListDecimal
            if kind == "itemize":
                bullet_styles = (
                    QTextListFormat.Style.ListDisc,
                    QTextListFormat.Style.ListCircle,
                    QTextListFormat.Style.ListSquare,
                )
                style = bullet_styles[(depth - 1) % len(bullet_styles)]

            fmt = QTextListFormat()
            fmt.setStyle(style)
            fmt.setIndent(depth)
            cursor.block().setUserData(
                _BlockMeta(
                    kind="list_item",
                    command=kind,
                    depth=depth,
                    raw=str(directives or ""),
                    source_line=source_line,
                )
            )
            self._reset_insertion_format(cursor)
            self._insert_inline_latex(cursor, item)
            cursor.createList(fmt)

    def refresh_graphic_resources(self) -> bool:
        """Reload only embedded graphic blocks without reparsing the document.

        iPad strokes can rewrite a PNG dozens of times per second. Rebuilding
        the whole Visual projection for each save is unnecessarily expensive
        for large LaTeX files, so update the image resources in place.
        """
        document = self.document()
        was_loading = self._loading
        was_modified = document.isModified()
        self._loading = True
        self._emit_timer.stop()
        refreshed = False
        try:
            block = document.firstBlock()
            while block.isValid():
                meta = block.userData()
                if isinstance(meta, _BlockMeta) and meta.kind == "graphic" and meta.display:
                    image_path = Path(meta.display).expanduser()
                    if not image_path.is_absolute() and self._source_path is not None:
                        image_path = self._source_path.parent / image_path
                    try:
                        image_path = image_path.resolve()
                    except OSError:
                        pass
                    image = QImage(str(image_path))
                    if not image.isNull():
                        stamp = image_path.stat().st_mtime_ns if image_path.exists() else 0
                        key = QUrl(f"ndgraphic:{image_path.as_posix()}:{stamp}")
                        document.addResource(QTextDocument.ResourceType.ImageResource, key, image)
                        available = max(self.viewport().width() - 70, 240)
                        scale = min(float(available) / max(float(image.width()), 1.0), 1.0)
                        iterator = block.begin()
                        while not iterator.atEnd():
                            fragment = iterator.fragment()
                            if fragment.isValid():
                                fmt = fragment.charFormat()
                                if fmt.isImageFormat():
                                    image_fmt = fmt.toImageFormat()
                                    image_fmt.setName(key.toString())
                                    image_fmt.setWidth(max(float(image.width()) * scale, 1.0))
                                    image_fmt.setHeight(max(float(image.height()) * scale, 1.0))
                                    cursor = QTextCursor(document)
                                    cursor.setPosition(fragment.position())
                                    cursor.setPosition(
                                        fragment.position() + fragment.length(),
                                        QTextCursor.MoveMode.KeepAnchor,
                                    )
                                    cursor.setCharFormat(image_fmt)
                                    refreshed = True
                            iterator += 1
                block = block.next()
        finally:
            document.setModified(was_modified)
            self._loading = was_loading
            self.viewport().update()
        return refreshed

    def _insert_graphic_block(
        self,
        cursor: QTextCursor,
        raw: str,
        graphic_path: str,
        source_line: int = 0,
    ) -> None:
        cursor.block().setUserData(
            _BlockMeta(
                kind="graphic",
                raw=raw,
                display=graphic_path,
                source_line=source_line,
            )
        )
        image_path = Path(graphic_path).expanduser()
        if not image_path.is_absolute() and self._source_path is not None:
            image_path = self._source_path.parent / image_path
        try:
            image_path = image_path.resolve()
        except OSError:
            pass
        image = QImage(str(image_path))
        if image.isNull():
            self._insert_raw_block(cursor, raw, source_line=source_line)
            return
        key = QUrl(f"ndgraphic:{image_path.as_posix()}:{image_path.stat().st_mtime_ns if image_path.exists() else 0}")
        self.document().addResource(QTextDocument.ResourceType.ImageResource, key, image)
        fmt = QTextImageFormat()
        fmt.setName(key.toString())
        available = max(self.viewport().width() - 70, 240)
        scale = min(float(available) / max(float(image.width()), 1.0), 1.0)
        fmt.setWidth(max(float(image.width()) * scale, 1.0))
        fmt.setHeight(max(float(image.height()) * scale, 1.0))
        cursor.insertImage(fmt)
        block_format = cursor.blockFormat()
        block_format.setTopMargin(8)
        block_format.setBottomMargin(8)
        cursor.setBlockFormat(block_format)

    def _insert_raw_block(
        self,
        cursor: QTextCursor,
        raw: str,
        source_line: int = 0,
    ) -> None:
        display = self._raw_display(raw)
        cursor.block().setUserData(
            _BlockMeta(
                kind="raw",
                raw=raw,
                display=display,
                source_line=source_line,
            )
        )
        cursor.insertText(display, self._raw_char_format())
        block_format = cursor.blockFormat()
        block_format.setLeftMargin(12)
        block_format.setRightMargin(12)
        block_format.setTopMargin(5)
        block_format.setBottomMargin(5)
        cursor.setBlockFormat(block_format)

    @staticmethod
    def _raw_display(raw: str) -> str:
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            return "LaTeX"
        if len(lines) == 1:
            display = lines[0]
        else:
            display = f"{lines[0]}  …  {lines[-1]}"
        if len(display) > 110:
            display = display[:107] + "…"
        return display

    @staticmethod
    def _raw_char_format() -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFontFamily("DejaVu Sans Mono")
        fmt.setForeground(QColor("#475467"))
        fmt.setBackground(QColor("#f2f4f7"))
        return fmt

    def _insert_inline_latex(self, cursor: QTextCursor, text: str) -> None:
        position = 0
        length = len(text)
        while position < length:
            parsed = self._match_known_inline(text, position)
            if parsed is not None:
                end, inner, fmt = parsed
                self._insert_inline_latex_with_format(cursor, inner, fmt)
                position = end
                continue

            raw = self._match_raw_inline(text, position)
            if raw is not None:
                end, raw_text = raw
                fmt = QTextCharFormat()
                fmt.setProperty(_RAW_LATEX_PROPERTY, raw_text)
                display_text = self._visual_raw_inline_text(raw_text)
                if display_text != raw_text:
                    fmt.setForeground(QColor("#101828"))
                    cursor.insertText(display_text, fmt)
                else:
                    fmt.setForeground(QColor("#175cd3"))
                    fmt.setBackground(QColor("#eff8ff"))
                    fmt.setFontFamily("DejaVu Sans Mono")
                    cursor.insertText(raw_text, fmt)
                position = end
                continue

            next_special = self._next_inline_special(text, position + 1)
            chunk = text[position:next_special]
            cursor.insertText(
                self._unescape_plain_text(chunk),
                QTextCharFormat(),
            )
            position = next_special

    def _insert_inline_latex_with_format(
        self,
        cursor: QTextCursor,
        inner: str,
        fmt: QTextCharFormat,
    ) -> None:
        start = cursor.position()
        self._insert_inline_latex(cursor, inner)
        end = cursor.position()
        selection = QTextCursor(cursor.document())
        selection.setPosition(start)
        selection.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        selection.mergeCharFormat(fmt)

    def _match_known_inline(self, text: str, start: int):
        commands = (
            ("\\textbf", "bold"),
            ("\\textit", "italic"),
            ("\\emph", "italic"),
        )
        for prefix, kind in commands:
            if text.startswith(prefix, start):
                brace = start + len(prefix)
                if brace < len(text) and text[brace] == "{":
                    inner, end = self._read_braced(text, brace)
                    if end is not None:
                        fmt = QTextCharFormat()
                        if kind == "bold":
                            fmt.setFontWeight(QFont.Weight.Bold)
                        else:
                            fmt.setFontItalic(True)
                        return end, inner, fmt

        if text.startswith("\\colorbox", start):
            brace = start + len("\\colorbox")
            if brace < len(text) and text[brace] == "{":
                color, after_color = self._read_braced(text, brace)
                if after_color is not None and after_color < len(text) and text[after_color] == "{":
                    inner, end = self._read_braced(text, after_color)
                    if end is not None:
                        fmt = QTextCharFormat()
                        fmt.setProperty(_LATEX_HIGHLIGHT_PROPERTY, color)
                        fmt.setBackground(QColor(self._HIGHLIGHT_TO_QCOLOR.get(color, "#fff6bf")))
                        return end, inner, fmt

        if text.startswith("\\textcolor", start):
            brace = start + len("\\textcolor")
            if brace < len(text) and text[brace] == "{":
                color, after_color = self._read_braced(text, brace)
                if after_color is not None and after_color < len(text) and text[after_color] == "{":
                    inner, end = self._read_braced(text, after_color)
                    if end is not None:
                        fmt = QTextCharFormat()
                        fmt.setProperty(_LATEX_TEXT_COLOR_PROPERTY, color)
                        fmt.setForeground(QColor(self._LATEX_TO_QCOLOR.get(color, "#101828")))
                        return end, inner, fmt
        return None

    @classmethod
    def _visual_raw_inline_text(cls, raw_text: str) -> str:
        if raw_text == r"\\":
            return "\u2028"
        direct = cls._SIMPLE_MATH_DISPLAY.get(raw_text)
        if direct is not None:
            return direct
        if raw_text.startswith("$") and raw_text.endswith("$"):
            inner = raw_text[1:-1].strip()
            direct = cls._SIMPLE_MATH_DISPLAY.get(inner)
            if direct is not None:
                return direct
        if raw_text.startswith(r"\(") and raw_text.endswith(r"\)"):
            inner = raw_text[2:-2].strip()
            direct = cls._SIMPLE_MATH_DISPLAY.get(inner)
            if direct is not None:
                return direct
        return raw_text

    def _match_raw_inline(self, text: str, start: int):
        if start >= len(text):
            return None
        if text[start] == "$":
            end = text.find("$", start + 1)
            if end >= 0:
                return end + 1, text[start : end + 1]
        if text.startswith("\\(", start):
            end = text.find("\\)", start + 2)
            if end >= 0:
                return end + 2, text[start : end + 2]
        if text.startswith(r"\\", start):
            return start + 2, r"\\"
        if text[start] != "\\":
            return None
        macro = re.match(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", text[start:])
        if macro is None:
            return None
        end = start + macro.end()
        # Preserve up to two immediate braced arguments as one raw chip.
        for _ in range(2):
            if end < len(text) and text[end] == "{":
                _, after = self._read_braced(text, end)
                if after is None:
                    break
                end = after
            else:
                break
        return end, text[start:end]

    @staticmethod
    def _next_inline_special(text: str, start: int) -> int:
        positions = [pos for pos in (text.find("\\", start), text.find("$", start)) if pos >= 0]
        return min(positions) if positions else len(text)

    @staticmethod
    def _read_braced(text: str, brace_index: int) -> tuple[str, int | None]:
        if brace_index >= len(text) or text[brace_index] != "{":
            return "", None
        depth = 0
        escaped = False
        for index in range(brace_index, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[brace_index + 1 : index], index + 1
        return "", None

    @staticmethod
    def _unescape_plain_text(text: str) -> str:
        replacements = {
            r"\%": "%",
            r"\&": "&",
            r"\_": "_",
            r"\#": "#",
            r"\$": "$",
            r"\{": "{",
            r"\}": "}",
            r'\"a': "ä",
            r'\"o': "ö",
            r'\"u': "ü",
            r'\"A': "Ä",
            r'\"O': "Ö",
            r'\"U': "Ü",
        }
        for escaped, plain in replacements.items():
            text = text.replace(escaped, plain)
        return text

    @staticmethod
    def _escape_plain_text(text: str) -> str:
        replacements = {
            "\\": r"\textbackslash{}",
            '"': r'\"',
            "%": r"\%",
            "&": r"\&",
            "_": r"\_",
            "#": r"\#",
            "$": r"\$",
            "{": r"\{",
            "}": r"\}",
        }
        return "".join(replacements.get(char, char) for char in text)

    def _serialize_inline_block(self, block) -> str:
        parts: list[str] = []
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if not fragment.isValid():
                iterator += 1
                continue
            fmt = fragment.charFormat()
            raw = fmt.property(_RAW_LATEX_PROPERTY)
            if raw:
                parts.append(str(raw))
                iterator += 1
                continue

            text = self._escape_plain_text(fragment.text())
            if not text:
                iterator += 1
                continue

            if (
                fmt.fontWeight() >= QFont.Weight.Bold
                and not bool(fmt.property(_VISUAL_HEADING_PROPERTY))
            ):
                text = f"\\textbf{{{text}}}"
            if fmt.fontItalic():
                text = f"\\textit{{{text}}}"
            latex_color = fmt.property(_LATEX_TEXT_COLOR_PROPERTY)
            if latex_color:
                text = f"\\textcolor{{{latex_color}}}{{{text}}}"
            highlight = fmt.property(_LATEX_HIGHLIGHT_PROPERTY)
            if highlight:
                text = f"\\colorbox{{{highlight}}}{{{text}}}"
            parts.append(text)
            iterator += 1
        return "".join(parts).strip()
