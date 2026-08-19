from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from nd_mind_mirror.core.completion.latex.latex_shortcut_provider import (
    LatexShortcut,
)


class LatexShortcutPopup(QFrame):
    """Non-focus-stealing shortcut chooser shown under the editor cursor."""

    def __init__(self, editor) -> None:
        super().__init__(
            editor,
            Qt.WindowType.ToolTip,
        )
        self._editor = editor
        self._matches: list[LatexShortcut] = []

        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )
        self.setObjectName("latexShortcutPopup")
        self.setStyleSheet(
            "QFrame#latexShortcutPopup {"
            "background: palette(base);"
            "border: 1px solid palette(mid);"
            "border-radius: 5px;"
            "}"
            "QLabel { padding: 3px 6px; font-weight: 600; }"
            "QListWidget { border: 0; outline: 0; }"
        )

        self._label = QLabel(
            "منظورت کدام است؟",
            self,
        )
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self._list = QListWidget(self)
        self._list.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )
        self._list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.addWidget(self._label)
        layout.addWidget(self._list)

        self.hide()

    def set_matches(
        self,
        matches: list[LatexShortcut],
    ) -> None:
        self._matches = list(matches)
        self._list.clear()

        for shortcut in self._matches:
            label = shortcut.trigger
            if shortcut.description:
                label += f"  —  {shortcut.description}"
            self._list.addItem(QListWidgetItem(label))

        if self._matches:
            self._list.setCurrentRow(0)

    def show_under_cursor(self) -> None:
        if not self._matches:
            self.hide()
            return

        row_height = max(
            self._list.sizeHintForRow(0),
            24,
        )
        visible_rows = min(len(self._matches), 8)
        list_height = row_height * visible_rows + 6
        width = max(
            360,
            min(
                620,
                self._list.sizeHintForColumn(0) + 44,
            ),
        )
        self._list.setFixedHeight(list_height)
        self.resize(
            width,
            list_height + self._label.sizeHint().height() + 14,
        )

        cursor_rect = self._editor.cursorRect()
        global_position = self._editor.viewport().mapToGlobal(
            cursor_rect.bottomLeft()
        )
        self.move(global_position)
        self.show()
        self.raise_()

    def move_selection(self, delta: int) -> None:
        if not self._matches:
            return

        current = self._list.currentRow()
        if current < 0:
            current = 0
        next_row = (current + int(delta)) % len(self._matches)
        self._list.setCurrentRow(next_row)
        self._list.scrollToItem(
            self._list.item(next_row),
            QAbstractItemView.ScrollHint.PositionAtCenter,
        )

    def selected_shortcut(self) -> LatexShortcut | None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._matches):
            return None
        return self._matches[row]
