"""Clickable Source/Visual bookmark gutter with persistent line-aligned bookmark ribbons."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPainter, QPen, QPolygon
from PySide6.QtWidgets import QMenu, QWidget


class BookmarkGutter(QWidget):
    """Thin clickable gutter shared by Source and Visual LaTeX views."""

    toggle_requested = Signal(int, int)
    rename_requested = Signal(int, int)
    remove_requested = Signal(int, int)

    def __init__(
        self,
        *,
        location_at_y: Callable[[int], tuple[int, int]],
        marker_y_for_location: Callable[[int, int], float | None],
        bookmarks_provider: Callable[[], list[dict[str, object]]],
        parent=None,
    ) -> None:
        """Create an interactive gutter that maps clicks and markers to source locations."""
        super().__init__(parent)
        self._location_at_y = location_at_y
        self._marker_y_for_location = marker_y_for_location
        self._bookmarks_provider = bookmarks_provider
        self.setFixedWidth(18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setToolTip(
            "Click to add/remove a bookmark. Right-click a bookmark to rename it."
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint a clear bookmark-ribbon icon directly opposite every visible bookmarked line."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        fill = QColor("#1565c0")
        border = QColor("#0d47a1")
        guide = QColor("#64b5f6")
        guide.setAlpha(190)

        for bookmark in self._bookmarks_provider():
            try:
                line = int(bookmark.get("line", 0))
                column = int(bookmark.get("column", 1))
            except (TypeError, ValueError):
                continue
            if line <= 0:
                continue

            y = self._marker_y_for_location(line, column)
            if y is None:
                continue
            center_y = int(round(float(y)))
            if center_y < -12 or center_y > self.height() + 12:
                continue

            painter.setPen(QPen(guide, 1))
            painter.drawLine(1, center_y, max(self.width() - 1, 1), center_y)

            top = center_y - 8
            bottom = center_y + 8
            left = 3
            right = max(self.width() - 3, left + 8)
            notch_x = (left + right) // 2
            notch_y = bottom - 5
            ribbon = QPolygon(
                [
                    QPoint(left, top),
                    QPoint(right, top),
                    QPoint(right, bottom),
                    QPoint(notch_x, notch_y),
                    QPoint(left, bottom),
                ]
            )
            pen = QPen(border)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(fill)
            painter.drawPolygon(ribbon)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Toggle bookmarks with left-click and expose rename/remove actions with right-click."""
        y = int(event.position().y())
        existing = self._bookmark_near_y(y)
        if existing is not None:
            line = int(existing.get("line", 1))
            column = int(existing.get("column", 1))
        else:
            line, column = self._location_at_y(y)
            line, column = max(int(line), 1), max(int(column), 1)

        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_requested.emit(line, column)
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            if existing is None:
                add_action = menu.addAction("Add Bookmark")
                chosen = menu.exec(event.globalPosition().toPoint())
                if chosen == add_action:
                    self.toggle_requested.emit(line, column)
            else:
                rename_action = menu.addAction("Rename Bookmark…")
                remove_action = menu.addAction("Remove Bookmark")
                chosen = menu.exec(event.globalPosition().toPoint())
                if chosen == rename_action:
                    self.rename_requested.emit(line, column)
                elif chosen == remove_action:
                    self.remove_requested.emit(line, column)
            event.accept()
            return
        super().mousePressEvent(event)

    def _bookmark_near_y(self, y: int) -> dict[str, object] | None:
        """Return the closest bookmark marker within the gutter's click tolerance."""
        best = None
        best_distance = 10.0
        for bookmark in self._bookmarks_provider():
            try:
                line = int(bookmark.get("line", 0))
                column = int(bookmark.get("column", 1))
            except (TypeError, ValueError):
                continue
            marker_y = self._marker_y_for_location(line, column)
            if marker_y is None:
                continue
            distance = abs(float(marker_y) - float(y))
            if distance <= best_distance:
                best = bookmark
                best_distance = distance
        return best
