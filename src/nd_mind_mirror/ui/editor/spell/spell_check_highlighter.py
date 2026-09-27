"""Wave-underline presentation for misspelled words."""

from __future__ import annotations

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from nd_mind_mirror.ui.editor.decoration.editor_decoration_properties import (
    EditorDecorationProperties,
)


class SpellCheckHighlighter:
    """Maintain spell-check ExtraSelections without disturbing other layers."""

    _COLOR = QColor("#d93025")

    def apply(self, widget, ranges: list[tuple[int, int]]) -> None:
        selections = self._without_own(widget)
        maximum = max(widget.document().characterCount() - 1, 0)
        for start, end in ranges:
            if end <= start:
                continue
            cursor = QTextCursor(widget.document())
            cursor.setPosition(max(0, min(int(start), maximum)))
            cursor.setPosition(
                max(0, min(int(end), maximum)),
                QTextCursor.MoveMode.KeepAnchor,
            )
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setUnderlineColor(self._COLOR)
            selection.format.setUnderlineStyle(
                QTextCharFormat.UnderlineStyle.SpellCheckUnderline
            )
            selection.format.setProperty(EditorDecorationProperties.PERSISTENT, True)
            selection.format.setProperty(EditorDecorationProperties.SPELL_CHECK, True)
            selections.append(selection)
        widget.setExtraSelections(selections)
        widget.viewport().update()

    def clear(self, widget) -> None:
        widget.setExtraSelections(self._without_own(widget))
        widget.viewport().update()

    @staticmethod
    def _without_own(widget):
        return [
            selection
            for selection in widget.extraSelections()
            if not bool(
                selection.format.property(EditorDecorationProperties.SPELL_CHECK)
            )
        ]
