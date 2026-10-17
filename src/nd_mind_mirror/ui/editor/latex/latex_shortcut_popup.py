from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nd_mind_mirror.core.completion.latex.latex_shortcut_provider import (
    LatexShortcut,
)


class LatexShortcutPopup(QFrame):
    """Non-focus-stealing chooser with explicit outside-event dismissal."""

    shortcut_selected = Signal(object)

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
        self._list.itemClicked.connect(self._select_clicked_shortcut)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.addWidget(self._label)
        layout.addWidget(self._list)

        self.hide()

    def showEvent(self, event: QEvent) -> None:
        """Watch global dismissal events only while the popup is displayed."""
        super().showEvent(event)
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

    def hideEvent(self, event: QEvent) -> None:
        """Avoid per-event overhead for inactive editors and closed tabs."""
        application = QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        super().hideEvent(event)

    def eventFilter(self, watched, event: QEvent) -> bool:
        """Dismiss the tooltip on actions outside it, including Esc elsewhere.

        A Qt ToolTip does not have the automatic outside-click lifecycle of a
        QMenu. Watching only the editor's keyPressEvent leaves a separate top-
        level popup stranded when focus, tabs, or the scroll position changes.
        """
        if not self.isVisible():
            return False

        event_type = event.type()
        if event_type == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.hide()
                return True
            return False

        if event_type in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonDblClick,
            QEvent.Type.Wheel,
            QEvent.Type.TouchBegin,
        ):
            if isinstance(watched, QWidget) and (
                watched is self or self.isAncestorOf(watched)
            ):
                return False
            self.hide()
            return False

        if event_type == QEvent.Type.FocusOut and watched is self._editor:
            focused = QApplication.focusWidget()
            if focused is not None and focused is not self._editor and not self.isAncestorOf(focused):
                self.hide()
        elif event_type in (
            QEvent.Type.Hide,
            QEvent.Type.Close,
        ) and watched in (self._editor, self._editor.window()):
            self.hide()
        elif event_type == QEvent.Type.ApplicationDeactivate:
            self.hide()
        return False

    def _select_clicked_shortcut(self, item: QListWidgetItem) -> None:
        """Apply a mouse-selected shortcut and dismiss its floating chooser."""
        row = self._list.row(item)
        if 0 <= row < len(self._matches):
            self.shortcut_selected.emit(self._matches[row])
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
