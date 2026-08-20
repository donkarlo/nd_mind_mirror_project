from pathlib import Path
import re

from PySide6.QtCore import QMimeData, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QKeyEvent, QResizeEvent, QTextCursor
from PySide6.QtWidgets import QCompleter, QInputDialog

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
from nd_mind_mirror.core.bookmark.bookmark_anchor_relocator import BookmarkAnchorRelocator
from nd_mind_mirror.graphic.core.document_manager import GraphicDocumentManager
from nd_mind_mirror.graphic.core.bridge_notifier import GraphicBridgeNotifier
from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.editor.bookmark.bookmark_gutter import BookmarkGutter
from nd_mind_mirror.ui.editor.latex.latex_shortcut_popup import (
    LatexShortcutPopup,
)
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor
from nd_mind_mirror.ui.highlighter.latex.latex_syntax_highlighter import (
    LatexSyntaxHighlighter,
)


class LatexEditor(TextEditor):
    content_changed = Signal(str)
    modification_changed = Signal(bool)
    active_cursor_changed = Signal()
    active_view_changed = Signal()
    bookmarks_changed = Signal(object)

    def __init__(
        self,
        completions: list[str],
        source_path: str | Path,
        app_settings: YamlSettings,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._app_settings = app_settings
        self._source_path = Path(
            source_path
        ).expanduser().resolve()
        self._completions = list(completions)
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
        self._syncing_cursor_views = False
        self._bookmarks: list[dict[str, object]] = []
        self._bookmark_relocator = BookmarkAnchorRelocator()
        self._bookmark_relocation_timer = QTimer(self)
        self._bookmark_relocation_timer.setSingleShot(True)
        self._bookmark_relocation_timer.setInterval(180)
        self._bookmark_relocation_timer.timeout.connect(self._relocate_bookmarks)
        self._source_padding = (10, 10, 10)
        self._visual_padding = (14, 16, 16)
        self._graphic_manager = GraphicDocumentManager()
        self._graphic_notifier: GraphicBridgeNotifier | None = None

        self.apply_settings(app_settings)

        self.setPlaceholderText(
            "Open a .tex file from the filesystem or File -> Open."
        )

        self._highlighter = LatexSyntaxHighlighter(
            self.document()
        )

        # The source QTextEdit remains the canonical document.  Visual mode is
        # an overlay which serializes supported rich edits back into this same
        # source document, so file saving, preview rendering, structure parsing
        # and external-file synchronization all continue to use one source of
        # truth.
        self._edit_mode = "source"
        self._visual_dirty = True
        self._syncing_from_visual = False
        self._visual_editor = LatexVisualEditor(self)
        self._visual_editor.apply_text_preferences(
            font_family=app_settings.editor_font_family,
            font_size=app_settings.editor_visual_font_size,
            font_min_size=app_settings.editor_font_min_size,
            font_max_size=app_settings.editor_font_max_size,
            line_height_percent=app_settings.editor_visual_line_height_percent,
        )
        self._visual_editor.apply_content_padding(
            top=app_settings.editor_visual_padding_top,
            left=app_settings.editor_visual_padding_left + 18,
            right=app_settings.editor_visual_padding_right,
        )
        self._visual_editor.configure_update_debounce(
            normal_ms=app_settings.editor_visual_update_debounce_ms,
            large_document_threshold_chars=(
                app_settings.editor_visual_large_document_threshold_chars
            ),
            large_document_ms=app_settings.editor_visual_large_document_debounce_ms,
        )
        self._visual_editor.configure_text_direction(
            mode=app_settings.editor_latex_text_direction,
            persian_ratio_threshold=app_settings.editor_latex_rtl_persian_ratio,
        )
        self._visual_editor.configure_source_assist(
            completions=self._completions,
            shortcuts=self._shortcuts,
            shortcut_min_prefix_length=self._shortcut_min_prefix_length,
        )
        self._visual_editor.hide()
        self._visual_editor.source_changed.connect(
            self._apply_visual_source
        )
        self._visual_editor.graphic_requested.connect(
            self._handle_graphic_request
        )
        self._visual_editor.cursorPositionChanged.connect(
            self._on_visual_cursor_changed
        )
        self._visual_editor.selectionChanged.connect(
            self._on_visual_cursor_changed
        )
        self._visual_editor.verticalScrollBar().valueChanged.connect(
            lambda _value: self._on_visual_view_changed()
        )

        self._source_bookmark_gutter = BookmarkGutter(
            location_at_y=self._source_location_at_y,
            marker_y_for_location=self._source_marker_y_for_location,
            bookmarks_provider=lambda: list(self._bookmarks),
            parent=self.viewport(),
        )
        self._visual_bookmark_gutter = BookmarkGutter(
            location_at_y=self._visual_editor.source_location_at_view_y,
            marker_y_for_location=self._visual_editor.marker_y_for_source_location,
            bookmarks_provider=lambda: list(self._bookmarks),
            parent=self._visual_editor.viewport(),
        )
        for gutter in (self._source_bookmark_gutter, self._visual_bookmark_gutter):
            gutter.toggle_requested.connect(self._toggle_bookmark)
            gutter.rename_requested.connect(self._rename_bookmark)
            gutter.remove_requested.connect(self._remove_bookmark)
            gutter.show()
            gutter.raise_()
        self._position_bookmark_gutters()

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
        self.textChanged.connect(self._schedule_bookmark_relocation)
        self.cursorPositionChanged.connect(self._on_source_cursor_changed)
        self.selectionChanged.connect(self._on_source_cursor_changed)
        self.verticalScrollBar().valueChanged.connect(
            lambda _value: self._on_source_view_changed()
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
        self._app_settings = app_settings
        self._graphic_manager = GraphicDocumentManager(
            directory_name=app_settings.graphic_directory_name,
            width_ratio=app_settings.graphic_width_ratio,
            canvas_width=app_settings.graphic_canvas_width,
            canvas_height=app_settings.graphic_canvas_height,
        )
        self._graphic_notifier = GraphicBridgeNotifier(
            workspace_root=app_settings.search_default_path,
            bridge_http_url=app_settings.graphic_bridge_http_url,
            token=app_settings.graphic_bridge_token,
        )
        self._direction_resolver.set_preferences(
            mode=app_settings.editor_latex_text_direction,
            persian_ratio_threshold=(
                app_settings.editor_latex_rtl_persian_ratio
            ),
        )
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
        self._source_padding = (
            app_settings.editor_source_padding_top,
            app_settings.editor_source_padding_left,
            app_settings.editor_source_padding_right,
        )
        self._visual_padding = (
            app_settings.editor_visual_padding_top,
            app_settings.editor_visual_padding_left,
            app_settings.editor_visual_padding_right,
        )
        self.apply_content_padding(
            top=self._source_padding[0],
            left=self._source_padding[1] + 18,
            right=self._source_padding[2],
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
        if hasattr(self, "_visual_editor"):
            self._visual_editor.apply_text_preferences(
                font_family=app_settings.editor_font_family,
                font_size=app_settings.editor_visual_font_size,
                font_min_size=app_settings.editor_font_min_size,
                font_max_size=app_settings.editor_font_max_size,
                line_height_percent=(
                    app_settings.editor_visual_line_height_percent
                ),
            )
            self._visual_editor.apply_content_padding(
                top=self._visual_padding[0],
                left=self._visual_padding[1] + 18,
                right=self._visual_padding[2],
            )
            self._visual_editor.configure_update_debounce(
                normal_ms=app_settings.editor_visual_update_debounce_ms,
                large_document_threshold_chars=(
                    app_settings.editor_visual_large_document_threshold_chars
                ),
                large_document_ms=(
                    app_settings.editor_visual_large_document_debounce_ms
                ),
            )
            self._visual_editor.configure_text_direction(
                mode=app_settings.editor_latex_text_direction,
                persian_ratio_threshold=app_settings.editor_latex_rtl_persian_ratio,
            )
            self._visual_editor.configure_source_assist(
                completions=self._completions,
                shortcuts=self._shortcuts,
                shortcut_min_prefix_length=self._shortcut_min_prefix_length,
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
        self._visual_dirty = True
        if self._edit_mode == "visual":
            self._refresh_visual_projection()

        self.content_changed.emit(content)
        self.modification_changed.emit(False)

    @property
    def edit_mode(self) -> str:
        return self._edit_mode

    def set_edit_mode(self, mode: str) -> None:
        requested = "visual" if str(mode).strip().lower() == "visual" else "source"
        if requested == self._edit_mode:
            if requested == "visual":
                self._visual_editor.setFocus()
            else:
                self.setFocus()
            return

        if requested == "visual":
            source_cursor = self.textCursor()
            anchor = self._source_location_for_position(source_cursor.anchor())
            position = self._source_location_for_position(source_cursor.position())
            self._refresh_visual_projection()
            self._edit_mode = "visual"
            self._visual_editor.setGeometry(self.rect())
            self._visual_editor.show()
            self._visual_editor.raise_()
            self._visual_bookmark_gutter.raise_()
            self.setFocusProxy(self._visual_editor)
            self._syncing_cursor_views = True
            try:
                self._visual_editor.set_selection_from_source_locations(
                    anchor, position, ensure_visible=True
                )
            finally:
                self._syncing_cursor_views = False
            self._visual_editor.setFocus()
        else:
            anchor, position = self._visual_editor.source_selection_locations()
            self._edit_mode = "source"
            self.setFocusProxy(None)
            self._visual_editor.hide()
            self._syncing_cursor_views = True
            try:
                self._set_source_selection_from_locations(anchor, position)
            finally:
                self._syncing_cursor_views = False
            self.ensureCursorVisible()
            self.setFocus()
        self.active_cursor_changed.emit()
        self.active_view_changed.emit()

    def go_to_source_location(
        self, line_number: int, column: int = 1, align_top: bool = True
    ) -> None:
        if self._edit_mode == "visual":
            self._visual_editor.go_to_source_location(
                line_number, column, align_top=align_top
            )
            return
        self._go_to_source_location(
            line_number, column, align_top=align_top
        )

    def go_to_line(
        self,
        line_number: int,
        align_top: bool = True,
    ) -> None:
        """Navigate Structure clicks in whichever LaTeX view is visible."""
        if self._edit_mode == "visual":
            self._visual_editor.go_to_source_location(
                line_number,
                1,
                align_top=align_top,
            )
            return
        super().go_to_line(line_number, align_top=align_top)

    def _go_to_source_location(
        self,
        line_number: int,
        column: int = 1,
        align_top: bool = False,
    ) -> None:
        block = self.document().findBlockByNumber(
            max(int(line_number) - 1, 0)
        )
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        cursor.setPosition(
            block.position()
            + min(max(int(column) - 1, 0), len(block.text()))
        )
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        if align_top:
            rectangle = self.cursorRect(cursor)
            scrollbar = self.verticalScrollBar()
            scrollbar.setValue(scrollbar.value() + rectangle.top())
        self.setFocus()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Expose Insert/Edit in iPad directly from the source context click."""
        click_cursor = self.cursorForPosition(event.pos())
        click_position = click_cursor.position()
        existing = self._graphic_manager.find_reference(
            self.toPlainText(),
            self._source_path,
            click_position,
        )

        menu = self.createStandardContextMenu()
        menu.addSeparator()
        graphic_action = menu.addAction(
            "Edit image in iPad…"
            if existing is not None
            else "Insert image in iPad…"
        )
        chosen = menu.exec(event.globalPos())
        if chosen != graphic_action:
            return
        current = self.textCursor()
        if not current.hasSelection():
            self.setTextCursor(click_cursor)
        line, column = self.active_source_location()
        self._handle_graphic_request(line, column)

    def _handle_graphic_request(self, line_number: int, column: int = 1) -> None:
        source = self.toPlainText()
        position = self._source_position_for_location((line_number, column))
        existing = self._graphic_manager.find_reference(
            source,
            self._source_path,
            position,
        )
        if existing is not None:
            self._request_ipad_open(existing.sidecar_path, operation="update")
            return

        document = self._graphic_manager.create_for_source(self._source_path)
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        self.setTextCursor(cursor)

        # Insert the exact source form used by Mind Mirror for iPad images:
        # \begin{figure}[H]
        #     \centering
        #     \includegraphics[width=0.9\textwidth]{graphic.png}
        # \end{figure}
        self._insert_figure(document.tex_reference)
        self.document().setModified(True)
        self._visual_dirty = True
        self._request_ipad_open(document.sidecar_path, operation="insert")
        if self._edit_mode == "visual":
            target_line = self.active_source_location()[0]
            self._refresh_visual_projection()
            self._visual_editor.go_to_source_location(target_line, 1, align_top=False)
        self.active_cursor_changed.emit()

    def _request_ipad_open(self, sidecar_path: Path, *, operation: str) -> None:
        if self._graphic_notifier is None:
            return
        try:
            self._graphic_notifier.request_open(sidecar_path, operation=operation)
        except (OSError, ValueError):
            # The graphic may live outside the configured workspace. The PNG
            # remains valid LaTeX; only the live iPad open request is skipped.
            return

    def refresh_visual_graphics(self) -> None:
        """Reload image resources after the iPad/Dropbox rewrites a PNG."""
        self._visual_dirty = True
        if self._edit_mode != "visual":
            return
        anchor, position = self._visual_editor.source_selection_locations()
        self._refresh_visual_projection()
        self._visual_editor.set_selection_from_source_locations(
            anchor, position, ensure_visible=False
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_visual_editor"):
            self._visual_editor.setGeometry(self.rect())
        self._position_bookmark_gutters()

    def _refresh_visual_projection(self) -> None:
        if not self._visual_dirty and self._visual_editor.document().blockCount() > 0:
            return
        self._visual_editor.load_source(self.toPlainText(), self._source_path)
        self._visual_dirty = False

    def _apply_visual_source(self, source: str) -> None:
        # Visual serialization is semantic rather than indentation-preserving.
        # Format it before replacing the canonical source so switching back to
        # Source never leaves every line at column zero and never requires a
        # manual Ctrl+Shift+F repair.
        formatted_source = self._formatter.format(source)
        if self._syncing_from_visual or formatted_source == self.toPlainText():
            return
        visual_anchor, visual_position = self._visual_editor.source_selection_locations()
        self._syncing_from_visual = True
        self._syncing_cursor_views = True
        try:
            cursor = QTextCursor(self.document())
            cursor.beginEditBlock()
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.insertText(formatted_source)
            cursor.endEditBlock()
            self._set_source_selection_from_locations(
                visual_anchor, visual_position
            )
            self.document().setModified(True)
            self._visual_dirty = False
        finally:
            self._syncing_cursor_views = False
            self._syncing_from_visual = False
        if self._edit_mode == "visual":
            self.active_cursor_changed.emit()

    def _source_location_for_position(self, position: int) -> tuple[int, int]:
        maximum = max(self.document().characterCount() - 1, 0)
        position = max(0, min(int(position), maximum))
        block = self.document().findBlock(position)
        if not block.isValid():
            return 1, 1
        return block.blockNumber() + 1, position - block.position() + 1

    def _source_position_for_location(self, location: tuple[int, int]) -> int:
        line, column = location
        block = self.document().findBlockByNumber(max(int(line) - 1, 0))
        if not block.isValid():
            return 0
        return block.position() + min(max(int(column) - 1, 0), len(block.text()))

    def _set_source_selection_from_locations(
        self, anchor: tuple[int, int], position: tuple[int, int]
    ) -> None:
        cursor = QTextCursor(self.document())
        cursor.setPosition(self._source_position_for_location(anchor))
        cursor.setPosition(
            self._source_position_for_location(position),
            QTextCursor.MoveMode.KeepAnchor,
        )
        self.setTextCursor(cursor)

    def active_source_location(self) -> tuple[int, int]:
        if self._edit_mode == "visual":
            return self._visual_editor.current_source_location()
        return self._source_location_for_position(self.textCursor().position())

    def active_preview_highlight_text(self) -> str:
        """Return the exact visible edit target for Preview highlighting.

        A selection always wins over the caret. Without a selection the word
        touching the caret is returned. In whitespace/punctuation, a compact
        four-character neighborhood (two logical characters on either side
        when available) is used so Preview still has a local target.
        """
        if self._edit_mode == "visual":
            cursor = self._visual_editor.textCursor()
            return self._preview_target_for_cursor(cursor, visual=True)
        return self._preview_target_for_cursor(self.textCursor(), visual=False)

    @classmethod
    def _preview_target_for_cursor(cls, cursor: QTextCursor, *, visual: bool) -> str:
        if cursor.hasSelection():
            selected = cursor.selectedText().replace("\u2029", " ").strip()
            if not visual:
                selected = cls._preview_visible_source_text(selected)
            return cls._normalize_preview_target(selected)

        text = cursor.block().text()
        offset = max(0, min(cursor.positionInBlock(), len(text)))
        if not visual:
            # Plain prose in Source maps directly. For LaTeX-heavy lines the
            # cleanup below removes control syntax before PDF text search.
            raw_text = text
        else:
            raw_text = text

        word_re = re.compile(r"[^\W_]+(?:[’'‌-][^\W_]+)*", re.UNICODE)
        for match in word_re.finditer(raw_text):
            if match.start() <= offset <= match.end():
                target = match.group(0)
                if not visual:
                    target = cls._preview_visible_source_text(target)
                return cls._normalize_preview_target(target)

        # Empty place: keep at least two logical characters before and after
        # the caret whenever the line has enough text. Expand around whitespace
        # only as needed; do not jump to an unrelated word elsewhere.
        start = max(0, offset - 2)
        end = min(len(raw_text), offset + 2)
        if end - start < 4:
            if start == 0:
                end = min(len(raw_text), 4)
            elif end == len(raw_text):
                start = max(0, len(raw_text) - 4)
        target = raw_text[start:end]
        if not visual:
            target = cls._preview_visible_source_text(target)
        return cls._normalize_preview_target(target)

    @staticmethod
    def _preview_visible_source_text(text: str) -> str:
        value = str(text)
        value = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", value)
        value = value.replace("{", " ").replace("}", " ").replace("$", " ")
        value = re.sub(r"\\([%&_#$])", r"\1", value)
        return value

    @staticmethod
    def _normalize_preview_target(text: str) -> str:
        value = re.sub(r"\s+", " ", str(text)).strip()
        # Huge selections make Qt PDF search unnecessarily expensive. The
        # selected beginning is still a stable exact target in the Preview.
        return value[:240]

    def first_visible_source_position(self) -> tuple[int, int]:
        if self._edit_mode == "visual":
            return self._visual_editor.first_visible_source_position()
        return super().first_visible_source_position()

    def _on_source_cursor_changed(self) -> None:
        if self._syncing_cursor_views:
            return
        if self._edit_mode == "source":
            # Mirror source selection into an already-current Visual projection.
            if not self._visual_dirty and self._visual_editor.document().blockCount() > 0:
                cursor = self.textCursor()
                anchor = self._source_location_for_position(cursor.anchor())
                position = self._source_location_for_position(cursor.position())
                self._syncing_cursor_views = True
                try:
                    self._visual_editor.set_selection_from_source_locations(
                        anchor, position, ensure_visible=False
                    )
                finally:
                    self._syncing_cursor_views = False
            self.active_cursor_changed.emit()

    def _on_visual_cursor_changed(self) -> None:
        if self._syncing_cursor_views or self._edit_mode != "visual":
            return
        anchor, position = self._visual_editor.source_selection_locations()
        self._syncing_cursor_views = True
        try:
            self._set_source_selection_from_locations(anchor, position)
        finally:
            self._syncing_cursor_views = False
        self.active_cursor_changed.emit()

    def _on_source_view_changed(self) -> None:
        if self._edit_mode == "source":
            if hasattr(self, "_source_bookmark_gutter"):
                self._source_bookmark_gutter.update()
            self.active_view_changed.emit()

    def _on_visual_view_changed(self) -> None:
        if hasattr(self, "_visual_bookmark_gutter"):
            self._visual_bookmark_gutter.update()
        if self._edit_mode == "visual":
            self.active_view_changed.emit()

    def _position_bookmark_gutters(self) -> None:
        if hasattr(self, "_source_bookmark_gutter"):
            viewport = self.viewport()
            self._source_bookmark_gutter.setGeometry(0, 0, 18, viewport.height())
            self._source_bookmark_gutter.raise_()
        if hasattr(self, "_visual_bookmark_gutter"):
            viewport = self._visual_editor.viewport()
            self._visual_bookmark_gutter.setGeometry(0, 0, 18, viewport.height())
            self._visual_bookmark_gutter.raise_()

    def _source_location_at_y(self, y: int) -> tuple[int, int]:
        cursor = self.cursorForPosition(
            QPoint(max(24, self.viewport().width() // 2), int(y))
        )
        return (
            max(cursor.blockNumber() + 1, 1),
            max(cursor.positionInBlock() + 1, 1),
        )

    def _source_marker_y_for_location(
        self, line_number: int, column: int = 1
    ) -> float | None:
        block = self.document().findBlockByNumber(max(int(line_number) - 1, 0))
        if not block.isValid():
            return None
        cursor = QTextCursor(block)
        cursor.setPosition(
            block.position() + min(max(int(column) - 1, 0), len(block.text()))
        )
        rect = self.cursorRect(cursor)
        return float(rect.center().y())

    def set_bookmarks(self, bookmarks: list[dict[str, object]] | None) -> None:
        normalized: list[dict[str, object]] = []
        for raw in bookmarks or []:
            if not isinstance(raw, dict):
                continue
            try:
                line = max(int(raw.get("line", 1)), 1)
            except (TypeError, ValueError):
                line = 1
            try:
                column = max(int(raw.get("column", 1)), 1)
            except (TypeError, ValueError):
                column = 1
            normalized.append({
                "line": line,
                "column": column,
                "name": str(raw.get("name", "")).strip(),
                "anchor": str(raw.get("anchor", "")),
            })
        self._bookmarks, _changed = self._bookmark_relocator.relocate(
            normalized, self.toPlainText()
        )
        self._update_bookmark_gutters()

    def bookmarks(self) -> list[dict[str, object]]:
        return [dict(item) for item in self._bookmarks]

    def toggle_bookmark_at_cursor(self) -> None:
        line, column = self.active_source_location()
        self._toggle_bookmark(line, column)

    def _bookmark_for_location(
        self, line: int, column: int
    ) -> dict[str, object] | None:
        for bookmark in self._bookmarks:
            if (
                int(bookmark.get("line", -1)) == int(line)
                and int(bookmark.get("column", 1)) == int(column)
            ):
                return bookmark
        return None

    def _toggle_bookmark(self, line: int, column: int) -> None:
        existing = self._bookmark_for_location(line, column)
        if existing is not None:
            self._bookmarks.remove(existing)
        else:
            source_lines = self.toPlainText().splitlines() or [""]
            line = max(1, min(int(line), len(source_lines)))
            column = max(1, min(int(column), len(source_lines[line - 1]) + 1))
            self._bookmarks.append({
                "line": line,
                "column": column,
                "name": "",
                "anchor": self._bookmark_relocator.normalize_line(source_lines[line - 1]),
            })
            self._bookmarks.sort(
                key=lambda item: (
                    int(item.get("line", 1)), int(item.get("column", 1))
                )
            )
        self._emit_bookmarks_changed()

    def _rename_bookmark(self, line: int, column: int) -> None:
        bookmark = self._bookmark_for_location(line, column)
        if bookmark is None:
            return
        current = str(bookmark.get("name", ""))
        value, accepted = QInputDialog.getText(
            self, "Bookmark name", "Name:", text=current
        )
        if not accepted:
            return
        bookmark["name"] = str(value).strip()
        self._emit_bookmarks_changed()

    def _remove_bookmark(self, line: int, column: int) -> None:
        bookmark = self._bookmark_for_location(line, column)
        if bookmark is None:
            return
        self._bookmarks.remove(bookmark)
        self._emit_bookmarks_changed()

    def _schedule_bookmark_relocation(self) -> None:
        if self._bookmarks:
            self._bookmark_relocation_timer.start()

    def _relocate_bookmarks(self) -> None:
        relocated, changed = self._bookmark_relocator.relocate(
            self._bookmarks, self.toPlainText()
        )
        self._bookmarks = relocated
        self._update_bookmark_gutters()
        if changed:
            self.bookmarks_changed.emit(self.bookmarks())

    def _emit_bookmarks_changed(self) -> None:
        self._update_bookmark_gutters()
        self.bookmarks_changed.emit(self.bookmarks())

    def _update_bookmark_gutters(self) -> None:
        if hasattr(self, "_source_bookmark_gutter"):
            self._source_bookmark_gutter.update()
        if hasattr(self, "_visual_bookmark_gutter"):
            self._visual_bookmark_gutter.update()

    def reset_zoom_to_settings(self) -> None:
        """Restore Source and Visual zoom to the font size from settings.yaml."""
        self.reset_font_zoom()
        self._visual_editor.reset_font_zoom()
        if self._edit_mode == "visual":
            self._visual_editor.setFocus()
        else:
            self.setFocus()

    def mark_saved(self) -> None:
        self.document().setModified(False)

    def bold_selection(self) -> bool:
        if self._edit_mode == "visual":
            self._visual_editor.toggle_bold()
            return True
        return self._wrap_selected_text(
            prefix="\\textbf{",
            suffix="}",
        )

    def italic_selection(self) -> bool:
        if self._edit_mode == "visual":
            self._visual_editor.toggle_italic()
            return True
        return self._wrap_selected_text(
            prefix="\\textit{",
            suffix="}",
        )

    def text_color_selection(self, color: str, css_color: str | None = None) -> bool:
        latex_color = str(color).strip()
        if not latex_color:
            return False
        if self._edit_mode == "visual":
            self._visual_editor.set_text_color(latex_color, css_color)
            return True
        return self._wrap_selected_text(
            prefix=f"\\textcolor{{{latex_color}}}{{",
            suffix="}",
        )

    def set_heading(self, command: str) -> bool:
        command = str(command).strip().lower()
        allowed = {
            "part", "chapter", "section", "subsection",
            "subsubsection", "paragraph", "subparagraph",
        }
        if command not in allowed:
            return False
        if self._edit_mode == "visual":
            self._visual_editor.set_heading(command)
            return True
        cursor = self.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        if selected:
            cursor.insertText(f"\\{command}{{{selected}}}")
        else:
            insertion_start = cursor.position()
            value = f"\\{command}{{}}"
            cursor.insertText(value)
            cursor.setPosition(insertion_start + len(command) + 2)
            self.setTextCursor(cursor)
        self.setFocus()
        return True

    def set_list(self, kind: str) -> bool:
        environment = "enumerate" if str(kind) == "enumerate" else "itemize"
        if self._edit_mode == "visual":
            self._visual_editor.set_list(environment)
            return True
        cursor = self.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        lines = [line for line in selected.splitlines() if line.strip()] if selected else [""]
        items = "\n".join(f"    \\item {line}" for line in lines)
        replacement = f"\\begin{{{environment}}}\n{items}\n\\end{{{environment}}}"
        start = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        cursor.insertText(replacement)
        if not selected:
            cursor.setPosition(start + len(f"\\begin{{{environment}}}\n    \\item "))
            self.setTextCursor(cursor)
        self.setFocus()
        return True

    def highlight_selection(self, color: str, css_color: str | None = None) -> bool:
        latex_color = str(color).strip()
        if not latex_color:
            return False
        if self._edit_mode == "visual":
            self._visual_editor.set_highlight(latex_color, css_color)
            return True

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
        if self._handle_common_editor_shortcut(event):
            return

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

        list_continuation = self._indentation.list_item_continuation(
            text,
            original_position,
        )

        # Ordinary Enter preserves only source indentation. Inside an existing
        # itemize/enumerate/description item, Enter continues the list with a
        # sibling \item at exactly the same indentation level.
        indentation = self._indentation.leading_whitespace(current_line)
        next_prefix = (
            list_continuation
            if list_continuation is not None
            else indentation
        )

        cursor.beginEditBlock()
        cursor.insertText("\n")
        cursor.insertText(next_prefix)
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
        if not self._syncing_from_visual:
            self._visual_dirty = True
        self.content_changed.emit(
            self.toPlainText()
        )
