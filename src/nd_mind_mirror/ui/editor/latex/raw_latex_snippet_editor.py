from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QKeyEvent, QTextCursor
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QPlainTextEdit

from nd_mind_mirror.core.completion.latex.latex_shortcut_provider import (
    LatexShortcut,
    LatexShortcutProvider,
)
from nd_mind_mirror.ui.highlighter.latex.latex_syntax_highlighter import (
    LatexSyntaxHighlighter,
)


class RawLatexSnippetEditor(QPlainTextEdit):
    """Small source editor used by Visual mode's raw-LaTeX dialog.

    It deliberately mirrors the two most useful source-mode helpers without
    constructing a full editor tab: LaTeX command completion and the user's
    ``latex_shortcuts.yaml`` expansions (for example ``lis`` -> ``list``).
    """

    def __init__(
        self,
        *,
        completions: list[str] | tuple[str, ...] = (),
        shortcuts: list[LatexShortcut] | tuple[LatexShortcut, ...] = (),
        shortcut_min_prefix_length: int = 2,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._completions = tuple(str(item) for item in completions if str(item))
        self._shortcuts = tuple(shortcuts)
        self._shortcut_min_prefix_length = max(int(shortcut_min_prefix_length), 1)
        self._active_prefix = ""
        self._active_prefix_start = -1
        self._active_prefix_end = -1
        self._active_replacements: dict[str, str] = {}

        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        if font.pointSize() < 12:
            font.setPointSize(12)
        self.setFont(font)
        self.setTabStopDistance(32.0)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._highlighter = LatexSyntaxHighlighter(self.document())

        # ToolTip keeps keyboard focus in this editor.  ``Qt.Popup`` can
        # become the active popup window on Linux, swallowing Enter before
        # QPlainTextEdit.keyPressEvent gets a chance to accept the shortcut.
        self._popup = QListWidget(self)
        self._popup.setWindowFlags(
            Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
        )
        self._popup.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )
        self._popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._popup.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._popup.setMinimumWidth(360)
        self._popup.hide()
        self._popup.itemClicked.connect(self._accept_suggestion_item)
        self._popup.itemActivated.connect(self._accept_suggestion_item)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._popup.isVisible():
            key = event.key()
            if key == Qt.Key.Key_Down:
                self._move_popup_selection(1)
                event.accept()
                return
            if key == Qt.Key.Key_Up:
                self._move_popup_selection(-1)
                event.accept()
                return
            if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab}:
                self._accept_current_suggestion()
                event.accept()
                return
            if key == Qt.Key.Key_Escape:
                self._popup.hide()
                event.accept()
                return

        super().keyPressEvent(event)
        self._update_suggestions()

    def _prefix_span(self) -> tuple[str, int, int]:
        cursor = self.textCursor()
        absolute_end = cursor.position()
        in_block_end = cursor.positionInBlock()
        text = cursor.block().text()[:in_block_end]
        match = re.search(r"\\[A-Za-z@]*$", text)
        if match is None:
            match = re.search(r"[A-Za-z0-9_-]+$", text)
        if match is None:
            return "", absolute_end, absolute_end
        prefix = match.group(0)
        return prefix, absolute_end - len(prefix), absolute_end

    def _prefix(self) -> str:
        return self._prefix_span()[0]

    def _update_suggestions(self) -> None:
        prefix, prefix_start, prefix_end = self._prefix_span()
        self._active_prefix = prefix
        self._active_prefix_start = prefix_start
        self._active_prefix_end = prefix_end
        self._active_replacements.clear()
        labels: list[str] = []

        if prefix.startswith("\\"):
            for completion in self._completions:
                if completion.startswith(prefix):
                    label = completion
                    labels.append(label)
                    self._active_replacements[label] = completion
                    if len(labels) >= 30:
                        break
        elif len(prefix) >= self._shortcut_min_prefix_length:
            folded = prefix.casefold()
            for shortcut in self._shortcuts:
                if not shortcut.trigger.casefold().startswith(folded):
                    continue
                label = shortcut.trigger
                if shortcut.description:
                    label += f"  —  {shortcut.description}"
                labels.append(label)
                self._active_replacements[label] = shortcut.replacement
                if len(labels) >= 30:
                    break

        if not labels:
            self._popup.hide()
            return

        self._popup.clear()
        for label in labels:
            item = QListWidgetItem(label, self._popup)
            item.setData(
                Qt.ItemDataRole.UserRole,
                self._active_replacements.get(label, ""),
            )
        self._popup.setCurrentRow(0)
        row_height = max(self._popup.sizeHintForRow(0), 24)
        self._popup.resize(
            max(360, min(680, self.width() - 20)),
            min(8, len(labels)) * row_height + 8,
        )
        rect = self.cursorRect()
        position = self.mapToGlobal(rect.bottomLeft())
        self._popup.move(position)
        self._popup.show()
        self._popup.raise_()


    def _accept_suggestion_item(self, item: QListWidgetItem) -> None:
        row = self._popup.row(item)
        if row >= 0:
            self._popup.setCurrentRow(row)
        self._accept_current_suggestion()

    def _move_popup_selection(self, delta: int) -> None:
        count = self._popup.count()
        if count <= 0:
            return
        row = self._popup.currentRow()
        if row < 0:
            row = 0
        self._popup.setCurrentRow((row + int(delta)) % count)
        self._popup.scrollToItem(self._popup.currentItem())

    def _accept_current_suggestion(self) -> None:
        item = self._popup.currentItem()
        if item is None:
            self._popup.hide()
            return
        replacement = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(replacement, str) or not replacement:
            replacement = self._active_replacements.get(item.text())
        prefix = self._active_prefix or self._prefix()
        if replacement is None or not prefix:
            self._popup.hide()
            return

        cursor = self.textCursor()
        cursor.beginEditBlock()
        # Select the typed prefix by logical document positions.  Cursor
        # ``PreviousCharacter`` is a visual movement in bidirectional text and
        # can therefore leave ``lis`` behind in an RTL paragraph.
        end = self._active_prefix_end
        start = self._active_prefix_start
        if start < 0 or end < start or end != cursor.position():
            _current, start, end = self._prefix_span()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

        marker = LatexShortcutProvider.CURSOR_MARKER
        marker_index = replacement.find(marker)
        inserted = replacement.replace(marker, "")
        start = cursor.selectionStart()
        cursor.insertText(inserted)
        if marker_index >= 0:
            cursor.setPosition(start + marker_index)
        else:
            # Put the caret inside the first empty braces when a normal LaTeX
            # completion was chosen, e.g. ``\\section{}``.
            brace_index = inserted.find("{}")
            if brace_index >= 0:
                cursor.setPosition(start + brace_index + 1)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self._active_prefix = ""
        self._active_prefix_start = -1
        self._active_prefix_end = -1
        self._popup.hide()
