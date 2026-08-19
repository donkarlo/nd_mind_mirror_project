from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


class EditorFindReplaceBar(QWidget):
    query_changed = Signal(str)
    next_requested = Signal()
    previous_requested = Signal()
    replace_requested = Signal(str)
    close_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._replace_mode = False

        self._find_label = QLabel("Find:", self)
        self._find_edit = QLineEdit(self)
        self._find_edit.setPlaceholderText("Search in current tab")
        self._find_edit.textChanged.connect(self.query_changed.emit)
        self._find_edit.returnPressed.connect(self.next_requested.emit)

        self._previous_button = QPushButton("◀", self)
        self._previous_button.setFixedWidth(34)
        self._previous_button.setToolTip("Previous match")
        self._previous_button.clicked.connect(self.previous_requested.emit)

        self._next_button = QPushButton("▶", self)
        self._next_button.setFixedWidth(34)
        self._next_button.setToolTip("Next match")
        self._next_button.clicked.connect(self.next_requested.emit)

        self._status_label = QLabel("0 / 0", self)
        self._status_label.setMinimumWidth(58)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._replace_label = QLabel("Replace:", self)
        self._replace_edit = QLineEdit(self)
        self._replace_edit.setPlaceholderText("Replacement")
        self._replace_edit.returnPressed.connect(
            lambda: self.replace_requested.emit(self._replace_edit.text())
        )
        self._replace_button = QPushButton("Replace", self)
        self._replace_button.clicked.connect(
            lambda: self.replace_requested.emit(self._replace_edit.text())
        )

        self._close_button = QPushButton("×", self)
        self._close_button.setFixedWidth(34)
        self._close_button.setToolTip("Close find/replace (Esc)")
        self._close_button.clicked.connect(self.close_requested.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self._find_label)
        layout.addWidget(self._find_edit, 2)
        layout.addWidget(self._previous_button)
        layout.addWidget(self._next_button)
        layout.addWidget(self._status_label)
        layout.addWidget(self._replace_label)
        layout.addWidget(self._replace_edit, 2)
        layout.addWidget(self._replace_button)
        layout.addWidget(self._close_button)

        self.set_replace_mode(False)
        self.hide()

    @property
    def query(self) -> str:
        return self._find_edit.text()

    @property
    def replacement(self) -> str:
        return self._replace_edit.text()

    def set_replace_mode(self, enabled: bool) -> None:
        self._replace_mode = bool(enabled)
        self._replace_label.setVisible(self._replace_mode)
        self._replace_edit.setVisible(self._replace_mode)
        self._replace_button.setVisible(self._replace_mode)

    def show_for_mode(self, replace_mode: bool, initial_query: str = "") -> None:
        self.set_replace_mode(replace_mode)
        if initial_query and not self._find_edit.text():
            self._find_edit.setText(initial_query)
        self.show()
        self.raise_()
        self._find_edit.setFocus()
        self._find_edit.selectAll()

    def set_match_status(self, current: int, total: int) -> None:
        if total <= 0:
            self._status_label.setText("0 / 0")
        else:
            self._status_label.setText(f"{max(current, 1)} / {total}")
