from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class RecentFileSwitcher(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("recentFileSwitcher")
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAutoFillBackground(True)
        self.setMinimumWidth(520)
        self.setMaximumWidth(760)
        self.setStyleSheet(
            "QFrame#recentFileSwitcher {"
            "background: palette(window);"
            "border: 2px solid #4a90e2;"
            "border-radius: 10px;"
            "}"
            "QListWidget { border: 0; background: transparent; }"
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22.0)
        shadow.setOffset(0.0, 5.0)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        self._title = QLabel("Recent files", self)
        self._list = QListWidget(self)
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.currentRowChanged.connect(
            lambda row: QTimer.singleShot(
                0,
                self._ensure_current_visible,
            )
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.addWidget(self._title)
        layout.addWidget(self._list)

        self._paths: list[Path] = []
        self.hide()

    def begin(
        self,
        paths: list[Path],
        direction: int,
    ) -> None:
        self._paths = list(paths)
        self._list.clear()

        for path in self._paths:
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(
                Qt.ItemDataRole.UserRole,
                str(path),
            )
            self._list.addItem(item)

        if not self._paths:
            self.hide()
            return

        initial = (
            len(self._paths) - 1
            if direction < 0
            else 1
            if len(self._paths) > 1
            else 0
        )
        self._list.setCurrentRow(initial)
        self._resize_for_items()
        self._center_on_parent()
        self.show()
        self.raise_()
        QTimer.singleShot(
            0,
            self._ensure_current_visible,
        )

    def step(self, direction: int) -> None:
        count = self._list.count()
        if count <= 0:
            return

        current = self._list.currentRow()
        if current < 0:
            current = 0

        next_row = (
            current + (1 if direction >= 0 else -1)
        ) % count
        self._list.setCurrentRow(next_row)
        self._ensure_current_visible()

    def selected_path(self) -> Path | None:
        item = self._list.currentItem()
        if item is None:
            return None

        value = item.data(Qt.ItemDataRole.UserRole)
        if not value:
            return None

        return Path(str(value))

    def dismiss(self) -> None:
        self.hide()
        self._paths = []
        self._list.clear()

    def _resize_for_items(self) -> None:
        # Keep the switcher tall enough to scan a useful part of a 20-tab
        # working set while still auto-scrolling the selected row.
        visible_rows = max(
            1,
            min(self._list.count(), 12),
        )
        row_height = self._list.sizeHintForRow(0)
        if row_height <= 0:
            row_height = 30

        height = 72 + visible_rows * row_height
        parent = self.parentWidget()
        if parent is not None:
            height = min(
                height,
                max(parent.height() - 80, 180),
            )

        self.resize(
            min(
                max(parent.width() // 2, 520),
                760,
            )
            if parent is not None
            else 620,
            height,
        )

    def _ensure_current_visible(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return

        self._list.scrollToItem(
            item,
            QAbstractItemView.ScrollHint.PositionAtCenter,
        )

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return

        self.move(
            max(
                (parent.width() - self.width()) // 2,
                0,
            ),
            max(
                (parent.height() - self.height()) // 2,
                0,
            ),
        )
