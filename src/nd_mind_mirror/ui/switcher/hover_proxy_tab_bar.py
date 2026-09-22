"""Proxy tab bar with deterministic transient tab hover."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import QStyle, QStyleOptionTab, QStylePainter, QTabBar


class HoverProxyTabBar(QTabBar):
    """Paint tab hover as light purple without changing label text color."""

    _HOVER_COLOR = QColor("#eadfff")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selection_visible = True
        self._hovered_index = -1
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setChangeCurrentOnDrag(False)

    def set_selection_visible(self, visible: bool) -> None:
        value = bool(visible)
        if value == self._selection_visible:
            return
        self._selection_visible = value
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        index = self.tabAt(event.position().toPoint())
        if index != self._hovered_index:
            self._hovered_index = index
            self.update()

        if event.buttons() == Qt.MouseButton.NoButton:
            event.accept()
            return

        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        if self._hovered_index != -1:
            self._hovered_index = -1
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QStylePainter(self)

        for index in range(self.count()):
            option = QStyleOptionTab()
            self.initStyleOption(option, index)

            is_hovered = index == self._hovered_index
            option.state &= ~QStyle.StateFlag.State_MouseOver

            if is_hovered or not self._selection_visible:
                option.state &= ~QStyle.StateFlag.State_Selected
                option.state &= ~QStyle.StateFlag.State_HasFocus

            painter.drawControl(
                QStyle.ControlElement.CE_TabBarTabShape,
                option,
            )

            if is_hovered:
                painter.fillRect(
                    self.tabRect(index).adjusted(1, 1, -1, -1),
                    self._HOVER_COLOR,
                )

            painter.drawControl(
                QStyle.ControlElement.CE_TabBarTabLabel,
                option,
            )
