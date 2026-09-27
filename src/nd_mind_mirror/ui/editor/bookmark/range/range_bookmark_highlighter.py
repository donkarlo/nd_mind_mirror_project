"""Yellow Source/Visual presentation for canonical range bookmarks."""

from __future__ import annotations

from PySide6.QtGui import QColor, QTextCursor, QTextFormat
from PySide6.QtWidgets import QTextEdit

from nd_mind_mirror.core.bookmark.range.range_bookmark_position_mapper import (
    RangeBookmarkPositionMapper,
)
from nd_mind_mirror.ui.editor.decoration.editor_decoration_properties import (
    EditorDecorationProperties,
)


class RangeBookmarkHighlighter:
    """Paint range bookmarks only in the view that currently needs presentation."""

    _MARK_PROPERTY = int(QTextFormat.Property.UserProperty) + 4401
    _COLOR = QColor("#fff59d")

    def __init__(self, editor) -> None:
        self._editor = editor

    def refresh(self) -> None:
        if str(getattr(self._editor, "edit_mode", "source")) == "visual":
            self.refresh_visual()
            return
        self.refresh_source()

    def refresh_source(self) -> None:
        tracker = getattr(self._editor, "_range_bookmark_tracker", None)
        if tracker is None:
            return
        editor = self._editor
        if bool(getattr(editor, "source_is_windowed", False)):
            provider = getattr(editor, "visible_source_text", None)
            source = str(provider()) if callable(provider) else ""
        else:
            source = str(editor.toPlainText())
        self._apply_source(source, tracker.collection.items)

    def refresh_visual(self) -> None:
        tracker = getattr(self._editor, "_range_bookmark_tracker", None)
        visual = getattr(self._editor, "_visual_editor", None)
        if tracker is None or visual is None:
            return
        self._apply_visual(visual, tracker.source, tracker.collection.items)

    def _apply_source(self, source: str, bookmarks) -> None:
        editor = self._editor
        selections = self._without_own(editor)

        window_start = 0
        visible_text = source
        if bool(getattr(editor, "source_is_windowed", False)):
            window_start = max(int(getattr(editor, "source_window_start", 0)), 0)
        window_end = window_start + len(visible_text)

        for item in bookmarks:
            start = max(int(item.start_char), window_start)
            end = min(int(item.end_char), window_end)
            if end <= start:
                continue
            selections.append(
                self._selection(
                    editor,
                    start - window_start,
                    end - window_start,
                )
            )
        editor.setExtraSelections(selections)
        editor.viewport().update()

    def _apply_visual(self, visual, source: str, bookmarks) -> None:
        selections = self._without_own(visual)
        mapper = RangeBookmarkPositionMapper(source)
        source_window = getattr(visual, "_source_window", None)

        for item in bookmarks:
            start_location = mapper.location_for_offset(item.start_char)
            end_location = mapper.location_for_offset(item.end_char)

            if source_window is not None and bool(
                getattr(source_window, "virtualized", False)
            ):
                first_line = int(getattr(source_window, "window_start_line", 1))
                last_line = int(getattr(source_window, "window_end_line", first_line))
                if end_location[0] < first_line or start_location[0] > last_line:
                    continue
                if start_location[0] < first_line:
                    start_location = (first_line, 1)
                if end_location[0] > last_line:
                    end_offset = mapper.line_end_offset(last_line)
                    end_location = mapper.location_for_offset(end_offset)

            try:
                start = visual.visual_position_for_source_location(*start_location)
                end = visual.visual_position_for_source_location(*end_location)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                continue
            if end <= start:
                continue
            selections.append(self._selection(visual, start, end))

        visual.setExtraSelections(selections)
        visual.viewport().update()

    @classmethod
    def _selection(cls, widget, start: int, end: int):
        selection = QTextEdit.ExtraSelection()
        cursor = QTextCursor(widget.document())
        maximum = max(widget.document().characterCount() - 1, 0)
        cursor.setPosition(max(0, min(int(start), maximum)))
        cursor.setPosition(
            max(0, min(int(end), maximum)),
            QTextCursor.MoveMode.KeepAnchor,
        )
        selection.cursor = cursor
        selection.format.setBackground(cls._COLOR)
        selection.format.setProperty(cls._MARK_PROPERTY, True)
        selection.format.setProperty(EditorDecorationProperties.PERSISTENT, True)
        return selection

    @classmethod
    def _without_own(cls, widget):
        result = []
        for selection in widget.extraSelections():
            if bool(selection.format.property(cls._MARK_PROPERTY)):
                continue
            result.append(selection)
        return result
