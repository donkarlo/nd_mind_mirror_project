"""Keep large LaTeX documents responsive without changing their canonical text."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPoint, QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPalette, QTextCursor

from nd_mind_mirror.core.render.latex.latex_renderer import LatexRenderer
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor
from nd_mind_mirror.ui.panel.file_system.file_system_panel import FileSystemPanel
from nd_mind_mirror.ui.panel.structure.latex_structure_panel import LatexStructurePanel
from nd_mind_mirror.ui.search.thread.file_search_index_thread import FileSearchIndexThread
from nd_mind_mirror.ui.search.window.search_window import SearchWindow
from nd_mind_mirror.ui.window.main.late_runtime_fixes import LateRuntimeFixes
from nd_mind_mirror.ui.window.main.logical_line_number_overlay import LogicalLineNumberOverlay
from nd_mind_mirror.ui.window.main.main_window import MainWindow
from nd_mind_mirror.ui.window.main.persistent_editor_visuals import PersistentEditorVisuals
from nd_mind_mirror.ui.window.main.visual_window_controller import VisualWindowController


class LargeDocumentPerformanceController:
    """Install bounded Source/Visual editing plus low-latency Preview/search UI fixes."""

    _hook_installed = False
    _runtime_installed = False
    _SOURCE_VIRTUAL_THRESHOLD_CHARS = 80_000
    _SMALL_PREVIEW_THRESHOLD_CHARS = 60_000
    _SMALL_SOURCE_EMIT_MS = 25
    _SMALL_VISUAL_EMIT_MS = 55
    _SMALL_PREVIEW_DEBOUNCE_MS = 35
    _SOURCE_REWINDOW_DELAY_MS = 90
    _SOURCE_SCROLL_EDGE_RATIO = 0.08

    _original_latex_to_plain_text: Callable | None = None
    _original_latex_set_content: Callable | None = None
    _original_source_location_for_position: Callable | None = None
    _original_source_position_for_location: Callable | None = None
    _original_set_edit_mode: Callable | None = None
    _original_go_to_source_location: Callable | None = None
    _original_go_to_line: Callable | None = None
    _original_first_visible_source_position: Callable | None = None
    _original_view_state: Callable | None = None
    _original_restore_view_state: Callable | None = None
    _original_format_document: Callable | None = None
    _original_apply_visual_source: Callable | None = None
    _original_on_visual_cursor_changed: Callable | None = None
    _original_emit_content: Callable | None = None

    @classmethod
    def install_startup_hook(cls) -> None:
        """Run these patches after all older runtime patches, before widgets are built."""
        if cls._hook_installed:
            return
        original_install = LateRuntimeFixes.install_class_patches

        def install_class_patches(_late_cls) -> None:
            original_install()
            cls._install_runtime_patches()

        LateRuntimeFixes.install_class_patches = classmethod(install_class_patches)
        cls._hook_installed = True

    @classmethod
    def _install_runtime_patches(cls) -> None:
        if cls._runtime_installed:
            return
        cls._install_visual_virtualization_threshold()
        cls._install_source_virtualization()
        cls._install_structure_idle_fast_path()
        cls._install_preview_fast_path()
        cls._install_preview_disable_cleanup()
        cls._install_navigator_density()
        cls._install_double_shift_focus_fix()
        cls._install_global_line_number_overlay()
        cls._install_virtualized_bookmark_filter()
        cls._runtime_installed = True

    @staticmethod
    def _setting_int(editor: LatexEditor, key: str, default: int, minimum: int, maximum: int) -> int:
        settings = getattr(editor, "_app_settings", None)
        try:
            raw = settings._get("editor", key, default=default)
            value = int(raw)
        except (AttributeError, TypeError, ValueError):
            value = default
        return max(minimum, min(value, maximum))

    @classmethod
    def _install_visual_virtualization_threshold(cls) -> None:
        """Virtualize by text volume even when a giant document has only a few source lines."""
        def should_virtualize(controller_type, source: str, body_lines: list[str]) -> bool:
            if not body_lines:
                return False
            char_threshold = max(int(getattr(controller_type, "_MIN_VIRTUAL_SOURCE_CHARS", 24_000)), 1)
            line_threshold = max(int(getattr(controller_type, "_MIN_VIRTUAL_BODY_LINES", 220)), 1)
            return len(source) >= char_threshold or len(body_lines) >= line_threshold

        VisualWindowController._should_virtualize = classmethod(should_virtualize)

    @classmethod
    def _install_source_virtualization(cls) -> None:
        """Keep only the configured page window in the Source QTextDocument for large LaTeX files."""
        original_init = LatexEditor.__init__
        cls._original_latex_to_plain_text = LatexEditor.toPlainText
        cls._original_latex_set_content = LatexEditor.set_content
        cls._original_source_location_for_position = LatexEditor._source_location_for_position
        cls._original_source_position_for_location = LatexEditor._source_position_for_location
        cls._original_set_edit_mode = LatexEditor.set_edit_mode
        cls._original_go_to_source_location = LatexEditor._go_to_source_location
        cls._original_go_to_line = LatexEditor.go_to_line
        cls._original_first_visible_source_position = LatexEditor.first_visible_source_position
        cls._original_view_state = LatexEditor.view_state
        cls._original_restore_view_state = LatexEditor.restore_view_state
        cls._original_format_document = LatexEditor.format_document
        cls._original_apply_visual_source = LatexEditor._apply_visual_source
        cls._original_on_visual_cursor_changed = LatexEditor._on_visual_cursor_changed
        cls._original_emit_content = LatexEditor._emit_content

        def init(editor: LatexEditor, *args, **kwargs) -> None:
            original_init(editor, *args, **kwargs)
            editor._nd_full_source = ""
            editor._nd_source_virtualized = False
            editor._nd_source_window_loading = False
            editor._nd_source_before = ""
            editor._nd_source_after = ""
            editor._nd_source_window_start_line = 1
            editor._nd_source_window_end_line = 1
            editor._nd_source_window_start_offset = 0
            editor._nd_source_window_end_offset = 0
            timer = QTimer(editor)
            timer.setSingleShot(True)
            timer.setInterval(cls._SOURCE_REWINDOW_DELAY_MS)
            timer.timeout.connect(lambda item=editor: cls._rewindow_source_from_scroll(item))
            editor._nd_source_rewindow_timer = timer
            editor.textChanged.connect(lambda item=editor: cls._sync_source_window_to_full(item))
            editor.verticalScrollBar().valueChanged.connect(
                lambda _value, item=editor: cls._schedule_source_rewindow(item)
            )

        def to_plain_text(editor: LatexEditor) -> str:
            if bool(getattr(editor, "_nd_source_virtualized", False)):
                return str(getattr(editor, "_nd_full_source", ""))
            assert cls._original_latex_to_plain_text is not None
            return str(cls._original_latex_to_plain_text(editor))

        def set_content(editor: LatexEditor, content: str) -> None:
            source = str(content)
            focus_line = cls._current_global_line(editor)
            editor._nd_full_source = source
            if not cls._should_virtualize_source(editor, source):
                editor._nd_source_virtualized = False
                editor._nd_source_before = ""
                editor._nd_source_after = ""
                editor._nd_source_window_start_line = 1
                editor._nd_source_window_end_line = max(source.count("\n") + 1, 1)
                editor._nd_source_window_start_offset = 0
                editor._nd_source_window_end_offset = len(source)
                assert cls._original_latex_set_content is not None
                cls._original_latex_set_content(editor, source)
                return

            editor._nd_source_virtualized = True
            editor._bookmark_relocation_timer.setInterval(1200)
            cls._load_source_window(
                editor,
                focus_line=focus_line,
                preserve_modified=False,
            )
            editor._visual_dirty = True
            if getattr(editor, "_edit_mode", "source") == "visual":
                editor._refresh_visual_projection()
            editor.content_changed.emit(source)
            editor.modification_changed.emit(False)

        def source_location_for_position(editor: LatexEditor, position: int) -> tuple[int, int]:
            assert cls._original_source_location_for_position is not None
            line, column = cls._original_source_location_for_position(editor, position)
            if bool(getattr(editor, "_nd_source_virtualized", False)):
                line += max(int(getattr(editor, "_nd_source_window_start_line", 1)) - 1, 0)
            return max(int(line), 1), max(int(column), 1)

        def source_position_for_location(editor: LatexEditor, location: tuple[int, int]) -> int:
            assert cls._original_source_position_for_location is not None
            if not bool(getattr(editor, "_nd_source_virtualized", False)):
                return int(cls._original_source_position_for_location(editor, location))
            line, column = max(int(location[0]), 1), max(int(location[1]), 1)
            start_line = int(getattr(editor, "_nd_source_window_start_line", 1))
            end_line = int(getattr(editor, "_nd_source_window_end_line", start_line))
            if line < start_line:
                return 0
            if line > end_line:
                return max(editor.document().characterCount() - 1, 0)
            return int(
                cls._original_source_position_for_location(
                    editor,
                    (line - start_line + 1, column),
                )
            )

        def apply_visual_source(editor: LatexEditor, source: str) -> None:
            if not bool(getattr(editor, "_nd_source_virtualized", False)):
                assert cls._original_apply_visual_source is not None
                cls._original_apply_visual_source(editor, source)
                return
            value = str(source)
            current = str(getattr(editor, "_nd_full_source", ""))
            if editor._syncing_from_visual or value == current:
                return
            editor._syncing_from_visual = True
            try:
                editor._nd_full_source = value
                editor.document().setModified(True)
                editor._visual_dirty = False
            finally:
                editor._syncing_from_visual = False
            if getattr(editor, "_bookmarks", None):
                editor._bookmark_relocation_timer.start()
            interval = (
                editor._source_large_document_debounce_ms
                if len(value) >= editor._source_large_document_threshold_chars
                else editor._source_update_debounce_ms
            )
            editor._content_emit_timer.setInterval(int(interval))
            editor._content_emit_timer.start()
            if getattr(editor, "_edit_mode", "source") == "visual":
                editor.active_cursor_changed.emit()

        def on_visual_cursor_changed(editor: LatexEditor) -> None:
            if (
                bool(getattr(editor, "_nd_source_virtualized", False))
                and getattr(editor, "_edit_mode", "source") == "visual"
            ):
                if editor._syncing_cursor_views:
                    return
                editor.active_cursor_changed.emit()
                return
            assert cls._original_on_visual_cursor_changed is not None
            cls._original_on_visual_cursor_changed(editor)

        def set_edit_mode(editor: LatexEditor, mode: str) -> None:
            if not bool(getattr(editor, "_nd_source_virtualized", False)):
                assert cls._original_set_edit_mode is not None
                cls._original_set_edit_mode(editor, mode)
                return

            requested = "visual" if str(mode).strip().lower() == "visual" else "source"
            if requested == editor._edit_mode:
                if requested == "visual":
                    editor._visual_editor.setFocus()
                else:
                    editor.setFocus()
                return

            if requested == "visual":
                source_cursor = editor.textCursor()
                anchor = editor._source_location_for_position(source_cursor.anchor())
                position = editor._source_location_for_position(source_cursor.position())
                editor._refresh_visual_projection()
                editor._edit_mode = "visual"
                editor._visual_editor.setGeometry(editor.rect())
                editor._visual_editor.show()
                editor._visual_editor.raise_()
                editor._visual_bookmark_gutter.raise_()
                editor.setFocusProxy(editor._visual_editor)
                editor._syncing_cursor_views = True
                try:
                    editor._visual_editor.set_selection_from_source_locations(
                        anchor,
                        position,
                        ensure_visible=True,
                    )
                finally:
                    editor._syncing_cursor_views = False
                editor._visual_editor.setFocus()
            else:
                timer = editor._visual_editor._emit_timer
                if timer.isActive():
                    timer.stop()
                    editor._visual_editor._emit_serialized_source()
                anchor, position = editor._visual_editor.source_selection_locations()
                cls._load_source_window(
                    editor,
                    focus_line=max(int(position[0]), 1),
                    anchor_location=anchor,
                    position_location=position,
                    preserve_modified=True,
                )
                editor._edit_mode = "source"
                editor.setFocusProxy(None)
                editor._visual_editor.hide()
                editor.ensureCursorVisible()
                editor.setFocus()

            editor.active_cursor_changed.emit()
            editor.active_view_changed.emit()

        def go_to_source_location(
            editor: LatexEditor,
            line_number: int,
            column: int = 1,
            align_top: bool = False,
        ) -> None:
            if not bool(getattr(editor, "_nd_source_virtualized", False)):
                assert cls._original_go_to_source_location is not None
                cls._original_go_to_source_location(editor, line_number, column, align_top)
                return
            cls._ensure_source_line_loaded(editor, max(int(line_number), 1))
            start_line = int(editor._nd_source_window_start_line)
            local_line = max(int(line_number) - start_line, 0)
            block = editor.document().findBlockByNumber(local_line)
            if not block.isValid():
                return
            cursor = QTextCursor(block)
            cursor.setPosition(
                block.position() + min(max(int(column) - 1, 0), len(block.text()))
            )
            editor.setTextCursor(cursor)
            editor.ensureCursorVisible()
            if align_top:
                rectangle = editor.cursorRect(cursor)
                scrollbar = editor.verticalScrollBar()
                scrollbar.setValue(scrollbar.value() + rectangle.top())
            editor.setFocus()

        def go_to_line(editor: LatexEditor, line_number: int, align_top: bool = True) -> None:
            if getattr(editor, "_edit_mode", "source") == "visual":
                assert cls._original_go_to_line is not None
                cls._original_go_to_line(editor, line_number, align_top)
                return
            if bool(getattr(editor, "_nd_source_virtualized", False)):
                go_to_source_location(editor, line_number, 1, align_top)
                return
            assert cls._original_go_to_line is not None
            cls._original_go_to_line(editor, line_number, align_top)

        def first_visible_source_position(editor: LatexEditor) -> tuple[int, int]:
            if not bool(getattr(editor, "_nd_source_virtualized", False)):
                assert cls._original_first_visible_source_position is not None
                return cls._original_first_visible_source_position(editor)
            if getattr(editor, "_edit_mode", "source") == "visual":
                return editor._visual_editor.first_visible_source_position()
            cursor = editor.cursorForPosition(QPoint(2, 2))
            return editor._source_location_for_position(cursor.position())

        def view_state(editor: LatexEditor) -> dict[str, int]:
            if not bool(getattr(editor, "_nd_source_virtualized", False)):
                assert cls._original_view_state is not None
                return cls._original_view_state(editor)
            cursor = editor.textCursor()
            global_cursor = int(editor._nd_source_window_start_offset) + int(cursor.position())
            return {
                "cursor": max(global_cursor, 0),
                "vertical": int(editor.verticalScrollBar().value()),
                "horizontal": int(editor.horizontalScrollBar().value()),
            }

        def restore_view_state(editor: LatexEditor, state: dict | None) -> None:
            if not bool(getattr(editor, "_nd_source_virtualized", False)):
                assert cls._original_restore_view_state is not None
                cls._original_restore_view_state(editor, state)
                return
            if not isinstance(state, dict):
                return
            try:
                global_position = int(state.get("cursor", 0))
                vertical = int(state.get("vertical", 0))
                horizontal = int(state.get("horizontal", 0))
            except (TypeError, ValueError):
                return
            line, column = cls._location_for_global_offset(editor._nd_full_source, global_position)
            cls._load_source_window(
                editor,
                focus_line=line,
                anchor_location=(line, column),
                position_location=(line, column),
                preserve_modified=True,
            )
            editor.verticalScrollBar().setValue(vertical)
            editor.horizontalScrollBar().setValue(horizontal)

        def format_document(editor: LatexEditor) -> None:
            if not bool(getattr(editor, "_nd_source_virtualized", False)):
                assert cls._original_format_document is not None
                cls._original_format_document(editor)
                return
            line, column = editor.active_source_location()
            source = str(editor._nd_full_source)
            formatted = editor._formatter.format(source)
            if formatted == source:
                return
            editor._nd_full_source = formatted
            cls._load_source_window(
                editor,
                focus_line=line,
                anchor_location=(line, column),
                position_location=(line, column),
                preserve_modified=True,
            )
            editor.document().setModified(True)
            editor._visual_dirty = True
            editor._content_emit_timer.setInterval(editor._source_large_document_debounce_ms)
            editor._content_emit_timer.start()

        def emit_content(editor: LatexEditor) -> None:
            if bool(getattr(editor, "_nd_source_virtualized", False)):
                if not editor._syncing_from_visual:
                    editor._visual_dirty = True
                full_length = len(str(getattr(editor, "_nd_full_source", "")))
                interval = (
                    editor._source_large_document_debounce_ms
                    if full_length >= editor._source_large_document_threshold_chars
                    else editor._source_update_debounce_ms
                )
                editor._content_emit_timer.setInterval(int(interval))
                editor._content_emit_timer.start()
                return
            assert cls._original_emit_content is not None
            cls._original_emit_content(editor)
            try:
                length = editor.document().characterCount()
            except RuntimeError:
                return
            if length < cls._SMALL_PREVIEW_THRESHOLD_CHARS:
                editor._content_emit_timer.setInterval(cls._SMALL_SOURCE_EMIT_MS)
                editor._content_emit_timer.start()

        LatexEditor.__init__ = init
        LatexEditor.toPlainText = to_plain_text
        LatexEditor.set_content = set_content
        LatexEditor._source_location_for_position = source_location_for_position
        LatexEditor._source_position_for_location = source_position_for_location
        LatexEditor._apply_visual_source = apply_visual_source
        LatexEditor._on_visual_cursor_changed = on_visual_cursor_changed
        LatexEditor.set_edit_mode = set_edit_mode
        LatexEditor._go_to_source_location = go_to_source_location
        LatexEditor.go_to_line = go_to_line
        LatexEditor.first_visible_source_position = first_visible_source_position
        LatexEditor.view_state = view_state
        LatexEditor.restore_view_state = restore_view_state
        LatexEditor.format_document = format_document
        LatexEditor._emit_content = emit_content

    @classmethod
    def _should_virtualize_source(cls, editor: LatexEditor, source: str) -> bool:
        if editor.source_path.suffix.lower() not in {".tex", ".tikz"}:
            return False
        return len(source) >= cls._SOURCE_VIRTUAL_THRESHOLD_CHARS

    @classmethod
    def _current_global_line(cls, editor: LatexEditor) -> int:
        try:
            if getattr(editor, "_edit_mode", "source") == "visual":
                line, _column = editor._visual_editor.current_source_location()
                return max(int(line), 1)
            if bool(getattr(editor, "_nd_source_virtualized", False)):
                line, _column = editor._source_location_for_position(editor.textCursor().position())
                return max(int(line), 1)
            assert cls._original_source_location_for_position is not None
            line, _column = cls._original_source_location_for_position(
                editor,
                editor.textCursor().position(),
            )
            return max(int(line), 1)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return 1

    @classmethod
    def _source_window_bounds(
        cls,
        editor: LatexEditor,
        lines: list[str],
        focus_index: int,
    ) -> tuple[int, int]:
        count = len(lines)
        if count <= 0:
            return 0, 0
        focus = max(0, min(int(focus_index), count - 1))
        pages_above = cls._setting_int(editor, "visual_window_pages_above", 4, 0, 100)
        pages_below = cls._setting_int(editor, "visual_window_pages_below", 4, 0, 100)
        chars_per_page = cls._setting_int(
            editor,
            "visual_window_estimated_chars_per_page",
            2400,
            200,
            20000,
        )
        max_lines_per_page = cls._setting_int(
            editor,
            "visual_window_max_lines_per_page",
            45,
            1,
            2000,
        )

        start = focus
        consumed_chars = 0
        consumed_lines = 0
        while (
            start > 0
            and consumed_chars < pages_above * chars_per_page
            and consumed_lines < pages_above * max_lines_per_page
        ):
            start -= 1
            consumed_chars += len(lines[start])
            consumed_lines += 1

        end = focus + 1
        consumed_chars = 0
        consumed_lines = 0
        while (
            end < count
            and consumed_chars < pages_below * chars_per_page
            and consumed_lines < pages_below * max_lines_per_page
        ):
            consumed_chars += len(lines[end])
            consumed_lines += 1
            end += 1

        return max(start, 0), min(max(end, start + 1), count)

    @classmethod
    def _load_source_window(
        cls,
        editor: LatexEditor,
        *,
        focus_line: int,
        anchor_location: tuple[int, int] | None = None,
        position_location: tuple[int, int] | None = None,
        preserve_modified: bool,
    ) -> None:
        source = str(getattr(editor, "_nd_full_source", ""))
        lines = source.splitlines(keepends=True)
        if not lines:
            lines = [""]
        focus_index = max(0, min(int(focus_line) - 1, len(lines) - 1))
        start, end = cls._source_window_bounds(editor, lines, focus_index)
        before = "".join(lines[:start])
        window = "".join(lines[start:end])
        after = "".join(lines[end:])
        was_modified = bool(editor.document().isModified()) if preserve_modified else False
        signals_were_blocked = editor.signalsBlocked()

        editor._nd_source_before = before
        editor._nd_source_after = after
        editor._nd_source_window_start_line = start + 1
        editor._nd_source_window_end_line = start + max(len(lines[start:end]), 1)
        editor._nd_source_window_start_offset = len(before)
        editor._nd_source_window_end_offset = len(before) + len(window)
        editor._nd_source_window_loading = True
        editor.blockSignals(True)
        try:
            editor.setPlainText(window)
            editor.apply_line_height(editor._line_height_percent)
            editor.document().setModified(was_modified)
        finally:
            editor.blockSignals(signals_were_blocked)
            editor._nd_source_window_loading = False

        if anchor_location is not None and position_location is not None:
            editor._syncing_cursor_views = True
            try:
                editor._set_source_selection_from_locations(anchor_location, position_location)
            finally:
                editor._syncing_cursor_views = False

        overlay = getattr(editor, "_nd_logical_line_numbers", None)
        if overlay is not None:
            overlay._update_width()
            overlay._refresh()

    @classmethod
    def _sync_source_window_to_full(cls, editor: LatexEditor) -> None:
        if (
            not bool(getattr(editor, "_nd_source_virtualized", False))
            or bool(getattr(editor, "_nd_source_window_loading", False))
        ):
            return
        assert cls._original_latex_to_plain_text is not None
        window = str(cls._original_latex_to_plain_text(editor))
        before = str(getattr(editor, "_nd_source_before", ""))
        after = str(getattr(editor, "_nd_source_after", ""))
        editor._nd_full_source = before + window + after
        editor._nd_source_window_end_offset = len(before) + len(window)
        editor._nd_source_window_end_line = (
            int(editor._nd_source_window_start_line) + max(window.count("\n"), 0)
        )

    @classmethod
    def _ensure_source_line_loaded(cls, editor: LatexEditor, line_number: int) -> None:
        if not bool(getattr(editor, "_nd_source_virtualized", False)):
            return
        start = int(getattr(editor, "_nd_source_window_start_line", 1))
        end = int(getattr(editor, "_nd_source_window_end_line", start))
        if start <= int(line_number) <= end:
            return
        cls._load_source_window(
            editor,
            focus_line=int(line_number),
            preserve_modified=True,
        )

    @classmethod
    def _schedule_source_rewindow(cls, editor: LatexEditor) -> None:
        if (
            not bool(getattr(editor, "_nd_source_virtualized", False))
            or bool(getattr(editor, "_nd_source_window_loading", False))
            or getattr(editor, "_edit_mode", "source") != "source"
        ):
            return
        scrollbar = editor.verticalScrollBar()
        maximum = max(int(scrollbar.maximum()), 0)
        if maximum <= 0:
            return
        ratio = float(scrollbar.value()) / float(maximum)
        if ratio <= cls._SOURCE_SCROLL_EDGE_RATIO or ratio >= 1.0 - cls._SOURCE_SCROLL_EDGE_RATIO:
            timer = getattr(editor, "_nd_source_rewindow_timer", None)
            if timer is not None:
                timer.start()

    @classmethod
    def _rewindow_source_from_scroll(cls, editor: LatexEditor) -> None:
        if (
            not bool(getattr(editor, "_nd_source_virtualized", False))
            or bool(getattr(editor, "_nd_source_window_loading", False))
            or getattr(editor, "_edit_mode", "source") != "source"
        ):
            return
        scrollbar = editor.verticalScrollBar()
        maximum = max(int(scrollbar.maximum()), 0)
        if maximum <= 0:
            return
        ratio = float(scrollbar.value()) / float(maximum)
        start = int(editor._nd_source_window_start_line)
        end = int(editor._nd_source_window_end_line)
        total_lines = max(str(editor._nd_full_source).count("\n") + 1, 1)
        if ratio >= 1.0 - cls._SOURCE_SCROLL_EDGE_RATIO and end < total_lines:
            focus = min(end + 1, total_lines)
        elif ratio <= cls._SOURCE_SCROLL_EDGE_RATIO and start > 1:
            focus = max(start - 1, 1)
        else:
            return

        current_location = editor._source_location_for_position(editor.textCursor().position())
        cls._load_source_window(editor, focus_line=focus, preserve_modified=True)
        new_start = int(editor._nd_source_window_start_line)
        new_end = int(editor._nd_source_window_end_line)
        target = current_location if new_start <= current_location[0] <= new_end else (focus, 1)
        editor._go_to_source_location(target[0], target[1], align_top=False)

    @staticmethod
    def _location_for_global_offset(source: str, position: int) -> tuple[int, int]:
        maximum = max(len(source), 0)
        pos = max(0, min(int(position), maximum))
        line = source.count("\n", 0, pos) + 1
        previous_newline = source.rfind("\n", 0, pos)
        column = pos + 1 if previous_newline < 0 else pos - previous_newline
        return max(line, 1), max(column, 1)

    @classmethod
    def _install_structure_idle_fast_path(cls) -> None:
        """Skip an 800 KB structure rescan when ordinary prose changes inside one line."""
        original = LatexStructurePanel.set_document
        tokens = (
            "\\part",
            "\\chapter",
            "\\section",
            "\\subsection",
            "\\subsubsection",
            "\\paragraph",
            "\\subparagraph",
            "\\includegraphics",
            "\\caption",
            "\\begin{figure",
            "\\end{figure",
        )

        def set_document(panel: LatexStructurePanel, path, source: str, immediate: bool = False) -> None:
            value = str(source)
            try:
                file_path = Path(path).expanduser().resolve()
            except OSError:
                original(panel, path, source, immediate)
                return
            old = str(getattr(panel, "_source", ""))
            same_path = getattr(panel, "_path", None) == file_path
            if (
                not immediate
                and same_path
                and len(value) >= cls._SOURCE_VIRTUAL_THRESHOLD_CHARS
                and old
                and not cls._structure_change_requires_rescan(old, value, tokens)
            ):
                panel._source = value
                panel._path = file_path
                panel._label.setText(f"Structure — {file_path.name}")
                return
            original(panel, path, value, immediate)

        LatexStructurePanel.set_document = set_document

    @staticmethod
    def _structure_change_requires_rescan(old: str, new: str, tokens: tuple[str, ...]) -> bool:
        if old == new:
            return False
        limit = min(len(old), len(new))
        prefix = 0
        chunk = 4096
        while prefix + chunk <= limit and old[prefix:prefix + chunk] == new[prefix:prefix + chunk]:
            prefix += chunk
        while prefix < limit and old[prefix] == new[prefix]:
            prefix += 1

        suffix_limit = min(len(old) - prefix, len(new) - prefix)
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
        old_changed = old[prefix:old_end]
        new_changed = new[prefix:new_end]
        if "\n" in old_changed or "\n" in new_changed or "\\" in old_changed or "\\" in new_changed:
            return True

        def line_context(text: str, start: int, end: int) -> str:
            left = text.rfind("\n", 0, start) + 1
            right = text.find("\n", end)
            if right < 0:
                right = len(text)
            return text[left:right]

        context = line_context(old, prefix, old_end) + "\n" + line_context(new, prefix, new_end)
        return any(token in context for token in tokens)

    @classmethod
    def _install_preview_fast_path(cls) -> None:
        """Restore coalesced compiling and remove stacked debounce latency for small files."""
        original_compile = getattr(LateRuntimeFixes, "_original_compile_pending_source", None)
        if callable(original_compile):
            LatexRenderer._compile_pending_source = original_compile

        original_render = LatexRenderer.render
        original_visual_schedule = LatexVisualEditor._schedule_source_emit

        def render(renderer: LatexRenderer, source: str, source_path=None, immediate: bool = False) -> None:
            original_render(renderer, source, source_path=source_path, immediate=immediate)
            if (
                renderer.enabled
                and not immediate
                and len(str(source)) < cls._SMALL_PREVIEW_THRESHOLD_CHARS
                and renderer._timer.isActive()
            ):
                renderer._timer.setInterval(cls._SMALL_PREVIEW_DEBOUNCE_MS)
                renderer._timer.start()

        def schedule_visual_source_emit(editor: LatexVisualEditor) -> None:
            original_visual_schedule(editor)
            if (
                not editor._loading
                and editor._has_loaded_source
                and int(getattr(editor, "_source_char_count", 0)) < cls._SMALL_PREVIEW_THRESHOLD_CHARS
                and editor._emit_timer.isActive()
            ):
                editor._emit_timer.setInterval(cls._SMALL_VISUAL_EMIT_MS)
                editor._emit_timer.start()

        LatexRenderer.render = render
        LatexVisualEditor._schedule_source_emit = schedule_visual_source_emit

    @classmethod
    def _install_preview_disable_cleanup(cls) -> None:
        """When Preview is hidden, cancel every remaining Preview-specific timer/cache loop."""
        original_set_preview_enabled = MainWindow._set_preview_enabled
        original_sync_dependencies = MainWindow._sync_preview_dependency_changes

        def set_preview_enabled(window: MainWindow, enabled: bool, refresh: bool = True) -> None:
            original_set_preview_enabled(window, enabled, refresh)
            if bool(enabled):
                return
            for name in (
                "_preview_edit_highlight_timer",
                "_graphic_preview_refresh_timer",
            ):
                timer = getattr(window, name, None)
                if timer is not None:
                    timer.stop()
            window._pending_preview_edit_highlight = ""
            window._last_preview_edit_highlight = ""
            window._preview_dependency_signatures = {}

        def sync_preview_dependency_changes(window: MainWindow) -> None:
            if not bool(getattr(window, "_preview_enabled", False)):
                return
            original_sync_dependencies(window)

        MainWindow._set_preview_enabled = set_preview_enabled
        MainWindow._sync_preview_dependency_changes = sync_preview_dependency_changes

    @classmethod
    def _install_navigator_density(cls) -> None:
        """Use smaller folder/file icons and a clearer hierarchy indent like the supplied reference."""
        original_init = FileSystemPanel.__init__
        original_apply = FileSystemPanel.apply_settings

        def init(panel: FileSystemPanel, parent=None) -> None:
            original_init(panel, parent)
            panel._tree.setIconSize(QSize(14, 14))
            panel._tree.setIndentation(20)

        def apply_settings(
            panel: FileSystemPanel,
            indent_width: int,
            root_path,
            ignore_file_path,
            row_height: int = 24,
            latex_templates=None,
        ) -> None:
            original_apply(
                panel,
                indent_width=max(int(indent_width), 20),
                root_path=root_path,
                ignore_file_path=ignore_file_path,
                row_height=row_height,
                latex_templates=latex_templates,
            )
            panel._tree.setIconSize(QSize(14, 14))
            panel._tree.setIndentation(max(int(indent_width), 20))

        FileSystemPanel.__init__ = init
        FileSystemPanel.apply_settings = apply_settings

    @classmethod
    def _install_double_shift_focus_fix(cls) -> None:
        """Focus the query first and refresh the filename index without blocking initial keystrokes."""
        original_apply_index = SearchWindow._apply_index

        def rebuild_index(window: SearchWindow) -> None:
            window._index_generation += 1
            generation = window._index_generation
            same_root_index = (
                bool(window._index_ready)
                and bool(window._search_index)
                and getattr(window, "_nd_index_root_path", window._root_path) == window._root_path
            )
            window._generation += 1
            window._debounce_timer.stop()

            for thread in list(window._threads):
                if thread.isRunning():
                    thread.requestInterruption()

            old_index_thread = window._index_thread
            if old_index_thread is not None and old_index_thread.isRunning():
                old_index_thread.requestInterruption()

            if not same_root_index:
                window._index_ready = False
                window._search_index = []
                window._status_label.setText("Indexing search root...")
            elif not window._search_edit.text().strip():
                window._status_label.setText("Refreshing search index...")

            thread = FileSearchIndexThread(
                generation=generation,
                root_path=window._root_path,
                ignore_file_path=window._ignore_file_path,
                parent=window,
            )
            window._index_thread = thread
            thread.index_ready.connect(window._apply_index)
            thread.finished.connect(lambda item=thread: window._remove_index_thread(item))
            thread.start()

        def apply_index(window: SearchWindow, generation: int, entries: object) -> None:
            original_apply_index(window, generation, entries)
            if generation == window._index_generation:
                window._nd_index_root_path = window._root_path

        def show_and_focus(window: SearchWindow) -> None:
            window._center_on_parent()
            window.show()
            window._center_on_parent()
            window.raise_()
            window.activateWindow()
            window._search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
            window._search_edit.selectAll()
            if window._search_edit.text().strip():
                window._schedule_search()

            current_index_thread = window._index_thread
            if current_index_thread is None or not current_index_thread.isRunning():
                QTimer.singleShot(120, window.rebuild_index)

        SearchWindow.rebuild_index = rebuild_index
        SearchWindow._apply_index = apply_index
        SearchWindow.show_and_focus = show_and_focus

    @classmethod
    def _install_global_line_number_overlay(cls) -> None:
        """Show canonical line numbers even though Source holds only a window."""
        def update_width(overlay: LogicalLineNumberOverlay, *args) -> None:
            del args
            editor = overlay._editor
            if bool(getattr(editor, "_nd_source_virtualized", False)):
                total = max(str(getattr(editor, "_nd_full_source", "")).count("\n") + 1, 1)
            else:
                total = max(editor.document().blockCount(), 1)
            digits = max(2, len(str(total)))
            metrics = QFontMetricsF(editor.font())
            desired = max(
                overlay._MIN_WIDTH,
                int(math.ceil(metrics.horizontalAdvance("9" * digits))) + overlay._HORIZONTAL_PADDING,
            )
            if desired != overlay._gutter_width:
                overlay._gutter_width = desired
                margins = overlay._base_margins
                editor.setViewportMargins(
                    margins.left() + overlay._gutter_width,
                    margins.top(),
                    margins.right(),
                    margins.bottom(),
                )
            overlay._position()

        def paint_event(overlay: LogicalLineNumberOverlay, event) -> None:
            del event
            editor = overlay._editor
            painter = QPainter(overlay)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            palette = editor.palette()
            color = palette.color(QPalette.ColorRole.PlaceholderText)
            if not color.isValid():
                color = QColor("#7a7a7a")
            painter.setPen(color)
            font = editor.font()
            point_size = font.pointSizeF()
            if point_size > 0:
                font.setPointSizeF(max(point_size * 0.78, 7.0))
            painter.setFont(font)
            metrics = QFontMetricsF(font)
            viewport = editor.viewport()
            first_cursor = editor.cursorForPosition(QPoint(2, 0))
            block = first_cursor.block()
            if block.previous().isValid():
                block = block.previous()
            base = (
                max(int(getattr(editor, "_nd_source_window_start_line", 1)) - 1, 0)
                if bool(getattr(editor, "_nd_source_virtualized", False))
                else 0
            )
            viewport_height = float(viewport.height())
            while block.isValid():
                cursor = editor.textCursor()
                cursor.setPosition(block.position())
                rectangle = editor.cursorRect(cursor)
                top = float(rectangle.top())
                if top > viewport_height + metrics.height():
                    break
                if top + metrics.height() >= 0:
                    text_rect = QRectF(
                        0.0,
                        top,
                        float(max(overlay._gutter_width - 6, 1)),
                        float(max(metrics.height(), rectangle.height())),
                    )
                    painter.drawText(
                        text_rect,
                        int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
                        str(base + block.blockNumber() + 1),
                    )
                block = block.next()

        LogicalLineNumberOverlay._update_width = update_width
        LogicalLineNumberOverlay.paintEvent = paint_event

    @classmethod
    def _install_virtualized_bookmark_filter(cls) -> None:
        """Never map off-window Source bookmarks to the nearest loaded edge."""
        original = PersistentEditorVisuals._source_bookmark_selections.__func__

        def source_bookmark_selections(controller_type, editor: LatexEditor):
            if not bool(getattr(editor, "_nd_source_virtualized", False)):
                return original(controller_type, editor)
            start = int(getattr(editor, "_nd_source_window_start_line", 1))
            end = int(getattr(editor, "_nd_source_window_end_line", start))
            filtered = []
            original_bookmarks = editor._bookmarks
            try:
                editor._bookmarks = [
                    bookmark
                    for bookmark in original_bookmarks
                    if (
                        (locations := controller_type._bookmark_locations(bookmark)) is not None
                        and start <= locations[0][0] <= end
                        and start <= locations[1][0] <= end
                    )
                ]
                filtered = original(controller_type, editor)
            finally:
                editor._bookmarks = original_bookmarks
            return filtered

        PersistentEditorVisuals._source_bookmark_selections = classmethod(source_bookmark_selections)
