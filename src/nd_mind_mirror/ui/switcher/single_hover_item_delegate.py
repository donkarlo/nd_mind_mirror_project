"""Paint one transient hover row and restore every other row's background."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem, QStyledItemDelegate


class SingleHoverItemDelegate(QStyledItemDelegate):
    """Paint exactly one light-purple row; repaint all others with the normal background."""

    _HOVER_COLOR = QColor("#eadfff")

    def __init__(self, base_delegate, parent=None) -> None:
        super().__init__(parent)
        self._base_delegate = base_delegate
        self._hovered_index = QModelIndex()

    @property
    def hovered_index(self) -> QModelIndex:
        return QModelIndex(self._hovered_index)

    def set_hovered_index(self, index: QModelIndex) -> None:
        self._hovered_index = QModelIndex(index)

    def clear_hovered_index(self) -> None:
        self._hovered_index = QModelIndex()

    def paint(self, painter, option, index) -> None:
        clean = QStyleOptionViewItem(option)
        clean.state &= ~QStyle.StateFlag.State_MouseOver
        clean.state &= ~QStyle.StateFlag.State_Selected
        clean.state &= ~QStyle.StateFlag.State_HasFocus

        painter.save()
        painter.fillRect(
            clean.rect,
            self._HOVER_COLOR
            if self._same_index(index, self._hovered_index)
            else clean.palette.base(),
        )
        painter.restore()

        self._base_delegate.paint(painter, clean, index)

    def sizeHint(self, option, index):
        return self._base_delegate.sizeHint(option, index)

    @staticmethod
    def _same_index(left: QModelIndex, right: QModelIndex) -> bool:
        return (
            left.isValid()
            and right.isValid()
            and left.model() is right.model()
            and left.row() == right.row()
            and left.column() == right.column()
            and left.parent() == right.parent()
        )
