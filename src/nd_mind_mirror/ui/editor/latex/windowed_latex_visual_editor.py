from __future__ import annotations

from pathlib import Path

import yaml
from PySide6.QtCore import QTimer

from nd_mind_mirror.ui.editor.latex.latex_visual_editor import (
    LatexVisualEditor,
    _BlockMeta,
)
from nd_mind_mirror.ui.editor.latex.visual_source_window import VisualSourceWindow


class WindowedLatexVisualEditor(LatexVisualEditor):
    """Render only a bounded slice of large sources while preserving full LaTeX.

    The parent ``LatexEditor`` remains the canonical complete source document.
    Only this Visual projection is virtualized. Structure, saving, Preview and
    all source-level operations therefore continue to receive the entire file.
    """

    def __init__(
        self,
        settings_path: str | Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._settings_path = Path(settings_path).expanduser().resolve()
        self._source_window = VisualSourceWindow()
        self._rewindowing = False
        self._scroll_edge_ratio = 0.14
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(90)
        self._scroll_timer.timeout.connect(self._rewindow_from_scroll)
        self.verticalScrollBar().valueChanged.connect(
            self._schedule_scroll_rewindow
        )
        self._reload_window_configuration()

    def load_source(
        self,
        source: str,
        source_path: str | Path | None = None,
    ) -> None:
        """Load a full small source or a cursor-centered slice of a large one."""
        self._reload_window_configuration()
        focus_line = self._preferred_focus_line()
        self._load_source_at_line(
            str(source),
            source_path,
            focus_line=focus_line,
        )

    def serialized_source(self) -> str:
        """Serialize Visual edits back into the untouched complete source."""
        serialized = super().serialized_source()
        return self._source_window.splice(serialized)

    def flush_pending_source_change(self) -> None:
        """Commit a pending Visual edit before this projection is hidden.

        Visual typing is debounced, but changing back to Source must be a
        synchronous boundary. Otherwise the Source view can expose the older
        canonical text while the last Visual keystrokes are still waiting in
        the timer.
        """
        if self._rewindowing or self._loading or not self._has_loaded_source:
            return
        if not self._emit_timer.isActive():
            return
        self._emit_timer.stop()
        self._emit_serialized_source()

    def hideEvent(self, event) -> None:
        self.flush_pending_source_change()
        super().hideEvent(event)

    def go_to_source_location(
        self,
        line_number: int,
        column: int = 1,
        align_top: bool = True,
    ) -> None:
        """Navigate to any Structure line, rewindowing Visual when necessary."""
        target_line = max(int(line_number), 1)
        if (
            self._source_window.virtualized
            and not self._source_window.contains_line(target_line)
        ):
            self._rewindow_to_line(target_line)
        super().go_to_source_location(
            target_line,
            column,
            align_top=align_top,
        )

    def set_selection_from_source_locations(
        self,
        anchor: tuple[int, int],
        position: tuple[int, int],
        *,
        ensure_visible: bool = True,
    ) -> None:
        """Keep Source/Visual selection sync valid across virtual windows."""
        target_line = max(int(position[0]), 1)
        if (
            self._source_window.virtualized
            and not self._source_window.contains_line(target_line)
        ):
            self._rewindow_to_line(target_line)
        super().set_selection_from_source_locations(
            anchor,
            position,
            ensure_visible=ensure_visible,
        )

    def marker_y_for_source_location(
        self,
        line_number: int,
        column: int = 1,
    ) -> float | None:
        """Do not force a distant Visual rewindow merely to draw a gutter marker."""
        if (
            self._source_window.virtualized
            and not self._source_window.contains_line(line_number)
        ):
            return None
        return super().marker_y_for_source_location(line_number, column)

    def _load_source_at_line(
        self,
        source: str,
        source_path: str | Path | None,
        *,
        focus_line: int,
    ) -> None:
        prefix, body, suffix = self._split_document(source)
        visual_source = self._source_window.select(
            full_source=source,
            prefix=prefix,
            body=body,
            suffix=suffix,
            focus_line=focus_line,
            source_path=source_path,
        )

        previous_sync = self._set_parent_cursor_sync(True)
        self._rewindowing = True
        try:
            super().load_source(visual_source, source_path)
            if self._source_window.virtualized:
                self._rebase_block_metadata(
                    self._source_window.window_start_line - 1
                )
                # Debounce must still reflect the complete source size, not the
                # small QTextDocument currently projected in Visual mode.
                self._source_char_count = len(source)
                self._update_emit_interval()
                self.document().setModified(False)
        finally:
            self._rewindowing = False
            self._restore_parent_cursor_sync(previous_sync)

    def _rewindow_to_line(self, line_number: int) -> None:
        if not self._source_window.virtualized or self._rewindowing:
            return
        full_source = self.serialized_source()
        source_path = self._source_window.source_path or self._source_path
        self._load_source_at_line(
            full_source,
            source_path,
            focus_line=max(int(line_number), 1),
        )

    def _preferred_focus_line(self) -> int:
        if self._source_window.virtualized and self.document().blockCount() > 0:
            try:
                line, _column = self.current_source_location()
                if self._source_window.contains_line(line):
                    return max(int(line), 1)
            except (AttributeError, RuntimeError):
                pass

        parent = self.parent()
        source_location = getattr(parent, "_source_location_for_position", None)
        text_cursor = getattr(parent, "textCursor", None)
        if callable(source_location) and callable(text_cursor):
            try:
                line, _column = source_location(text_cursor().position())
                return max(int(line), 1)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass
        return max(self._source_window.window_start_line, 1)

    def _schedule_scroll_rewindow(self, _value: int) -> None:
        if self._rewindowing or not self._source_window.virtualized:
            return
        scrollbar = self.verticalScrollBar()
        maximum = scrollbar.maximum()
        if maximum <= 0:
            return
        ratio = scrollbar.value() / maximum
        if ratio <= self._scroll_edge_ratio or ratio >= 1.0 - self._scroll_edge_ratio:
            self._scroll_timer.start()

    def _rewindow_from_scroll(self) -> None:
        if self._rewindowing or not self._source_window.virtualized:
            return
        scrollbar = self.verticalScrollBar()
        maximum = scrollbar.maximum()
        if maximum <= 0:
            return
        ratio = scrollbar.value() / maximum
        if self._scroll_edge_ratio < ratio < 1.0 - self._scroll_edge_ratio:
            return

        try:
            if ratio <= self._scroll_edge_ratio:
                line, column = self.first_visible_source_position()
            else:
                line, column = self.source_location_at_view_y(
                    max(self.viewport().height() - 4, 1)
                )
        except (AttributeError, RuntimeError):
            return

        line = max(int(line), 1)
        if not self._source_window.contains_line(line):
            return
        old_start = self._source_window.window_start_line
        old_end = self._source_window.window_end_line
        self._rewindow_to_line(line)
        if (
            old_start == self._source_window.window_start_line
            and old_end == self._source_window.window_end_line
        ):
            return
        super().go_to_source_location(
            line,
            column,
            align_top=False,
        )

    def _reload_window_configuration(self) -> None:
        data = {}
        try:
            loaded = yaml.safe_load(
                self._settings_path.read_text(encoding="utf-8")
            )
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, yaml.YAMLError):
            data = {}

        editor = data.get("editor", {})
        if not isinstance(editor, dict):
            editor = {}

        self._source_window.configure(
            threshold_chars=self._integer(
                editor.get("visual_large_document_threshold_chars"),
                120_000,
                minimum=10_000,
            ),
            pages_above=self._integer(
                editor.get("visual_window_pages_above"),
                4,
                minimum=0,
            ),
            pages_below=self._integer(
                editor.get("visual_window_pages_below"),
                4,
                minimum=0,
            ),
            estimated_chars_per_page=self._integer(
                editor.get("visual_window_estimated_chars_per_page"),
                2_400,
                minimum=200,
            ),
            min_lines_per_page=self._integer(
                editor.get(
                    "visual_window_min_lines_per_page",
                    editor.get("visual_window_min_lines_per_peage"),
                ),
                12,
                minimum=1,
            ),
            max_lines_per_page=self._integer(
                editor.get("visual_window_max_lines_per_page"),
                45,
                minimum=1,
            ),
            max_window_chars=self._integer(
                editor.get("visual_window_max_chars"),
                40_000,
                minimum=4_000,
            ),
        )
        self._scroll_edge_ratio = self._float(
            editor.get("visual_window_scroll_edge_ratio"),
            0.14,
            minimum=0.02,
            maximum=0.45,
        )
        self._scroll_timer.setInterval(
            self._integer(
                editor.get("visual_window_rewindow_delay_ms"),
                90,
                minimum=30,
            )
        )

    def _rebase_block_metadata(self, line_delta: int) -> None:
        delta = max(int(line_delta), 0)
        if delta == 0:
            return
        block = self.document().firstBlock()
        while block.isValid():
            data = block.userData()
            if isinstance(data, _BlockMeta):
                if data.source_line > 0:
                    data.source_line += delta
                if data.source_segments:
                    data.source_segments = [
                        (int(line) + delta, text)
                        for line, text in data.source_segments
                    ]
            block = block.next()

    def _set_parent_cursor_sync(self, value: bool):
        parent = self.parent()
        if parent is None or not hasattr(parent, "_syncing_cursor_views"):
            return None
        previous = bool(parent._syncing_cursor_views)
        parent._syncing_cursor_views = bool(value)
        return previous

    def _restore_parent_cursor_sync(self, previous) -> None:
        if previous is None:
            return
        parent = self.parent()
        if parent is not None and hasattr(parent, "_syncing_cursor_views"):
            parent._syncing_cursor_views = bool(previous)

    @staticmethod
    def _integer(value, default: int, *, minimum: int) -> int:
        try:
            result = int(value)
        except (TypeError, ValueError):
            result = int(default)
        return max(result, int(minimum))

    @staticmethod
    def _float(
        value,
        default: float,
        *,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError):
            result = float(default)
        return max(float(minimum), min(result, float(maximum)))
