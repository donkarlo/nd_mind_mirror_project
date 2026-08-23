"""Install editor interaction, bounded-layout, and quiet-terminal fixes without duplicating editor state."""

from __future__ import annotations

from collections.abc import Callable
import logging
import sys

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QTextCursor

from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor
from nd_mind_mirror.ui.preview.pdf.selectable_pdf_view import SelectablePdfView
from nd_mind_mirror.ui.window.main.main_window import MainWindow


class _FilteredTerminalStream:
    """Forward terminal output except the repetitive search-context diagnostic lines."""

    def __init__(self, stream) -> None:
        """Wrap one existing stdout/stderr stream without changing its terminal identity."""
        self._stream = stream
        self._pending = ""

    @staticmethod
    def _is_noise(line: str) -> bool:
        """Recognize only the diagnostic pattern observed during Persian Visual editing."""
        normalized = str(line).strip().casefold()
        return normalized.startswith("search string ") and " not found in context " in normalized

    def write(self, text) -> int:
        """Buffer partial writes so a diagnostic is removed only after a full line is available."""
        value = str(text)
        self._pending += value
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            if not self._is_noise(line):
                self._stream.write(line + "\n")
        return len(value)

    def flush(self) -> None:
        """Flush pending non-noise text and then flush the wrapped stream."""
        if self._pending and not self._is_noise(self._pending):
            self._stream.write(self._pending)
        self._pending = ""
        self._stream.flush()

    def isatty(self) -> bool:
        """Preserve the wrapped stream's TTY status."""
        return bool(getattr(self._stream, "isatty", lambda: False)())

    def fileno(self) -> int:
        """Expose the wrapped stream's file descriptor for libraries that request it."""
        return int(self._stream.fileno())

    @property
    def encoding(self):
        """Expose the wrapped stream's encoding."""
        return getattr(self._stream, "encoding", "utf-8")

    @property
    def errors(self):
        """Expose the wrapped stream's error policy."""
        return getattr(self._stream, "errors", "strict")

    def __getattr__(self, name):
        """Delegate uncommon stream attributes to the original stream."""
        return getattr(self._stream, name)


class EditorInteractionEnhancements:
    """Patch existing editor hooks for layout, bookmarks, fast Visual sync, and Structure sync."""

    _installed = False
    _SOURCE_PAGES_ABOVE = 5
    _SOURCE_PAGES_BELOW = 5

    @classmethod
    def install(cls) -> None:
        """Install all enhancements exactly once before editor widgets are constructed."""
        if cls._installed:
            return
        cls._install_terminal_noise_filter()
        cls._install_preview_search_noise_guard()
        cls._install_source_layout_window()
        cls._install_fast_visual_source_sync()
        cls._install_source_bookmark_menu()
        cls._install_visual_bookmark_menu()
        cls._install_visual_layout_fixes()
        cls._install_scroll_structure_sync()
        cls._installed = True

    @classmethod
    def _install_terminal_noise_filter(cls) -> None:
        """Suppress only repetitive search-context diagnostics while preserving real errors."""
        del cls
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        if not isinstance(old_stdout, _FilteredTerminalStream):
            sys.stdout = _FilteredTerminalStream(old_stdout)
        if not isinstance(old_stderr, _FilteredTerminalStream):
            sys.stderr = _FilteredTerminalStream(old_stderr)

        root = logging.getLogger()
        for handler in list(root.handlers):
            if not isinstance(handler, logging.StreamHandler):
                continue
            stream = getattr(handler, "stream", None)
            try:
                if stream is old_stdout:
                    handler.setStream(sys.stdout)
                elif stream is old_stderr:
                    handler.setStream(sys.stderr)
            except (AttributeError, ValueError):
                continue

    @classmethod
    def _install_preview_search_noise_guard(cls) -> None:
        """Avoid Qt PDF text-search diagnostics for Arabic-script highlights it cannot map reliably."""
        del cls
        original: Callable = SelectablePdfView.set_edit_highlight

        def set_edit_highlight(view: SelectablePdfView, text: str) -> None:
            value = str(text or "")
            if any(EditorInteractionEnhancements._is_arabic_script_character(char) for char in value):
                value = ""
            original(view, value)

        SelectablePdfView.set_edit_highlight = set_edit_highlight

    @staticmethod
    def _is_arabic_script_character(char: str) -> bool:
        """Return whether one character belongs to Arabic-script ranges used by Persian."""
        if not char:
            return False
        code = ord(char)
        return (
            0x0600 <= code <= 0x08FF
            or 0xFB50 <= code <= 0xFDFF
            or 0xFE70 <= code <= 0xFEFF
        )

    @classmethod
    def _install_source_layout_window(cls) -> None:
        """Limit expensive Source presentation formatting to five viewport-pages around view/cursor."""
        original_init: Callable = TextEditor.__init__

        def init(editor: TextEditor, parent=None) -> None:
            original_init(editor, parent)
            timer = QTimer(editor)
            timer.setSingleShot(True)
            timer.setInterval(35)
            timer.timeout.connect(lambda item=editor: cls._apply_source_layout_window(item))
            editor._nd_source_layout_window_timer = timer
            editor.verticalScrollBar().valueChanged.connect(
                lambda _value, item=editor: cls._schedule_source_layout_window(item)
            )
            editor.cursorPositionChanged.connect(
                lambda item=editor: cls._schedule_source_layout_window(item)
            )

        def apply_block_layout_preferences(editor: TextEditor) -> None:
            cls._apply_source_layout_window(editor)

        TextEditor.__init__ = init
        TextEditor._apply_block_layout_preferences = apply_block_layout_preferences

    @classmethod
    def _schedule_source_layout_window(cls, editor: TextEditor) -> None:
        """Debounce Source presentation work while the user scrolls or moves the cursor."""
        del cls
        timer = getattr(editor, "_nd_source_layout_window_timer", None)
        if timer is not None:
            timer.start()

    @classmethod
    def _apply_source_layout_window(cls, editor: TextEditor) -> None:
        """Apply Source block layout only within five visible-page spans above and below focus."""
        document = editor.document()
        if document.blockCount() <= 0:
            return

        viewport_height = max(editor.viewport().height(), 1)
        top_cursor = editor.cursorForPosition(QPoint(2, 2))
        bottom_cursor = editor.cursorForPosition(QPoint(2, max(viewport_height - 2, 2)))
        top_line = max(top_cursor.blockNumber(), 0)
        bottom_line = max(bottom_cursor.blockNumber(), top_line)
        visible_blocks = max(bottom_line - top_line + 1, 12)

        cursor_line = max(editor.textCursor().blockNumber(), 0)
        if top_line <= cursor_line <= bottom_line:
            focus_line = cursor_line
        else:
            focus_line = (top_line + bottom_line) // 2

        start_line = max(
            focus_line - cls._SOURCE_PAGES_ABOVE * visible_blocks,
            0,
        )
        end_line = min(
            focus_line + cls._SOURCE_PAGES_BELOW * visible_blocks,
            max(document.blockCount() - 1, 0),
        )
        start_block = document.findBlockByNumber(start_line)
        end_block = document.findBlockByNumber(end_line)
        editor._apply_block_layout_range(start_block, end_block)

    @classmethod
    def _install_fast_visual_source_sync(cls) -> None:
        """Use a minimal source diff per Visual edit and defer full LaTeX formatting until Source is shown."""
        original_set_edit_mode: Callable = LatexEditor.set_edit_mode

        def apply_visual_source(editor: LatexEditor, source: str) -> None:
            current_source = editor.toPlainText()
            if editor._syncing_from_visual or source == current_source:
                return

            visual_anchor, visual_position = editor._visual_editor.source_selection_locations()
            start, old_end, replacement = cls._minimal_text_change(current_source, source)
            editor._syncing_from_visual = True
            editor._syncing_cursor_views = True
            try:
                cursor = QTextCursor(editor.document())
                cursor.beginEditBlock()
                cursor.setPosition(start)
                cursor.setPosition(old_end, QTextCursor.MoveMode.KeepAnchor)
                cursor.insertText(replacement)
                cursor.endEditBlock()
                editor._set_source_selection_from_locations(
                    visual_anchor,
                    visual_position,
                )
                editor.document().setModified(True)
                editor._visual_dirty = False
            finally:
                editor._syncing_cursor_views = False
                editor._syncing_from_visual = False
            if editor._edit_mode == "visual":
                editor.active_cursor_changed.emit()

        def set_edit_mode(editor: LatexEditor, mode: str) -> None:
            requested = "visual" if str(mode).strip().lower() == "visual" else "source"
            leaving_visual = editor._edit_mode == "visual" and requested == "source"
            if leaving_visual:
                timer = editor._visual_editor._emit_timer
                if timer.isActive():
                    timer.stop()
                    editor._visual_editor._emit_serialized_source()
                editor.format_document()
            original_set_edit_mode(editor, mode)

        LatexEditor._apply_visual_source = apply_visual_source
        LatexEditor.set_edit_mode = set_edit_mode

    @staticmethod
    def _minimal_text_change(old: str, new: str) -> tuple[int, int, str]:
        """Return one minimal replacement span using chunked prefix/suffix comparison."""
        if old == new:
            return 0, 0, ""

        limit = min(len(old), len(new))
        prefix = 0
        chunk = 4096
        while prefix + chunk <= limit and old[prefix:prefix + chunk] == new[prefix:prefix + chunk]:
            prefix += chunk
        while prefix < limit and old[prefix] == new[prefix]:
            prefix += 1

        old_remaining = len(old) - prefix
        new_remaining = len(new) - prefix
        suffix_limit = min(old_remaining, new_remaining)
        suffix = 0
        while (
            suffix + chunk <= suffix_limit
            and old[len(old) - suffix - chunk:len(old) - suffix]
            == new[len(new) - suffix - chunk:len(new) - suffix]
        ):
            suffix += chunk
        while (
            suffix < suffix_limit
            and old[len(old) - suffix - 1] == new[len(new) - suffix - 1]
        ):
            suffix += 1

        old_end = len(old) - suffix
        new_end = len(new) - suffix
        return prefix, old_end, new[prefix:new_end]

    @staticmethod
    def _append_bookmark_action(menu, editor, line: int, column: int) -> None:
        """Append one Bookmark Here action that reuses LatexEditor's existing bookmark store."""
        menu.addSeparator()
        action = menu.addAction("Bookmark Here")
        action.triggered.connect(
            lambda _checked=False, item=editor, row=int(line), col=int(column):
            item._toggle_bookmark(row, col)
        )

    @classmethod
    def _install_source_bookmark_menu(cls) -> None:
        """Show Bookmark Here in Source only when the user has selected text."""
        original: Callable = LatexEditor.createStandardContextMenu

        def create_standard_context_menu(editor: LatexEditor):
            menu = original(editor)
            cursor = editor.textCursor()
            if cursor.hasSelection():
                line, column = editor._source_location_for_position(
                    cursor.selectionStart()
                )
                cls._append_bookmark_action(menu, editor, line, column)
            return menu

        LatexEditor.createStandardContextMenu = create_standard_context_menu

    @classmethod
    def _install_visual_bookmark_menu(cls) -> None:
        """Show Bookmark Here in Visual only when the user has selected text."""
        original: Callable = LatexVisualEditor.createStandardContextMenu

        def create_standard_context_menu(editor: LatexVisualEditor):
            menu = original(editor)
            cursor = editor.textCursor()
            owner = editor.parentWidget()
            if cursor.hasSelection() and isinstance(owner, LatexEditor):
                line, column = editor.source_location_for_position(
                    cursor.selectionStart()
                )
                cls._append_bookmark_action(menu, owner, line, column)
            return menu

        LatexVisualEditor.createStandardContextMenu = create_standard_context_menu

    @classmethod
    def _install_visual_layout_fixes(cls) -> None:
        """Persist Visual padding across projection reloads and justify normal prose blocks."""
        original_padding: Callable = LatexVisualEditor.apply_content_padding
        original_load: Callable = LatexVisualEditor.load_source

        def apply_content_padding(
            editor: LatexVisualEditor,
            *,
            top: int = 0,
            left: int = 0,
            right: int = 0,
        ) -> None:
            editor._nd_visual_content_padding = (
                max(int(top), 0),
                max(int(left), 0),
                max(int(right), 0),
            )
            original_padding(
                editor,
                top=editor._nd_visual_content_padding[0],
                left=editor._nd_visual_content_padding[1],
                right=editor._nd_visual_content_padding[2],
            )

        def load_source(
            editor: LatexVisualEditor,
            source: str,
            source_path=None,
        ) -> None:
            original_load(editor, source, source_path)
            padding = getattr(editor, "_nd_visual_content_padding", None)
            if padding is not None:
                original_padding(
                    editor,
                    top=padding[0],
                    left=padding[1],
                    right=padding[2],
                )
            cls._justify_visual_prose(editor)

        LatexVisualEditor.apply_content_padding = apply_content_padding
        LatexVisualEditor.load_source = load_source

    @staticmethod
    def _justify_visual_prose(editor: LatexVisualEditor) -> None:
        """Use LaTeX-like full justification for paragraphs and list items in Visual mode."""
        document = editor.document()
        was_modified = document.isModified()
        was_loading = editor._loading
        editor._loading = True
        editor._emit_timer.stop()
        try:
            block = document.firstBlock()
            while block.isValid():
                meta = block.userData()
                kind = str(getattr(meta, "kind", "paragraph"))
                if kind in {"paragraph", "list_item"} and block.text().strip():
                    cursor = QTextCursor(block)
                    block_format = block.blockFormat()
                    block_format.setAlignment(Qt.AlignmentFlag.AlignJustify)
                    cursor.setBlockFormat(block_format)
                block = block.next()
            document.setModified(was_modified)
        finally:
            editor._loading = was_loading
        editor.viewport().update()

    @classmethod
    def _install_scroll_structure_sync(cls) -> None:
        """Drive Structure highlighting from the first visible source line during scrolling."""
        original: Callable = MainWindow._on_current_view_changed

        def on_current_view_changed(
            window: MainWindow,
            path: str,
            line: int,
            column: int,
        ) -> None:
            window._structure_panel.set_current_line(max(int(line), 1))
            original(window, path, line, column)

        MainWindow._on_current_view_changed = on_current_view_changed
