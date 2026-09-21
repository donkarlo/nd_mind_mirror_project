"""Transient hover presentation for native Pinned/Open overflow popups."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, QObject, QPoint, QRect
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QApplication,
    QMenu,
    QWidget,
)

from nd_mind_mirror.ui.switcher.single_hover_item_delegate import (
    SingleHoverItemDelegate,
)


class TabOverflowPopupHoverController(QObject):
    """Show purple only for the popup row currently under the pointer."""

    _MENU_STYLE = """
QMenu::item:selected {
    background-color: #eadfff;
}
"""

    def __init__(self, tab_bar, parent=None) -> None:
        super().__init__(parent or tab_bar)
        self._tab_bar = tab_bar
        self._application = QApplication.instance()
        self._tracked_menu: QMenu | None = None
        self._tracked_view: QAbstractItemView | None = None
        self._original_delegate: QAbstractItemDelegate | None = None
        self._hover_delegate: SingleHoverItemDelegate | None = None

        if self._application is not None:
            self._application.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        """Track hover from viewport mouse moves and restore the old row immediately."""
        event_type = event.type()

        if event_type == QEvent.Type.Show:
            if isinstance(watched, QMenu) and self._belongs_to_tab_bar(watched):
                self._configure_menu(watched)
            elif (
                isinstance(watched, QAbstractItemView)
                and self._belongs_to_tab_bar(watched)
            ):
                self._configure_item_view(watched)

        if isinstance(event, QMouseEvent):
            self._update_menu_hover(event)

        view = self._tracked_view
        if view is not None and watched is view.viewport():
            if event_type == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
                self._update_view_hover(event.position().toPoint())
            elif event_type in {QEvent.Type.Leave, QEvent.Type.HoverLeave}:
                self._set_view_hover(QModelIndex())

        if watched is self._tracked_menu:
            self._handle_menu_lifecycle(event_type)

        if view is not None and watched is view:
            self._handle_view_lifecycle(event_type)

        return super().eventFilter(watched, event)

    def _belongs_to_tab_bar(self, widget: QWidget) -> bool:
        """Accept only transient popups opened in the local band of this tab row."""
        if not widget.isWindow():
            return False

        bar_top_left = self._tab_bar.mapToGlobal(QPoint(0, 0))
        bar_rect = QRect(bar_top_left, self._tab_bar.size())
        popup_rect = widget.frameGeometry()
        band = bar_rect.adjusted(-48, -16, 96, 160)
        return band.intersects(popup_rect)

    def _configure_menu(self, menu: QMenu) -> None:
        self._tracked_menu = menu
        if self._MENU_STYLE.strip() not in menu.styleSheet():
            menu.setStyleSheet(menu.styleSheet() + self._MENU_STYLE)
        menu.setMouseTracking(True)
        menu.setActiveAction(None)
        menu.update()

    def _configure_item_view(self, view: QAbstractItemView) -> None:
        """Install one delegate and use viewport mouse moves as mouseenter/mouseout."""
        if self._tracked_view is not None and self._tracked_view is not view:
            self._restore_item_view()

        self._tracked_view = view
        self._original_delegate = view.itemDelegate()
        self._hover_delegate = SingleHoverItemDelegate(
            self._original_delegate,
            view,
        )
        view.setItemDelegate(self._hover_delegate)
        view.setMouseTracking(True)
        view.viewport().setMouseTracking(True)
        view.viewport().installEventFilter(self)
        self._set_view_hover(QModelIndex())

    def _update_view_hover(self, point: QPoint) -> None:
        view = self._tracked_view
        if view is None:
            return
        self._set_view_hover(view.indexAt(point))

    def _set_view_hover(self, index: QModelIndex) -> None:
        """Equivalent of mouseout/mouseover: restore old row, then paint only new row."""
        view = self._tracked_view
        delegate = self._hover_delegate
        if view is None or delegate is None:
            return

        previous = delegate.hovered_index
        current = QModelIndex(index)
        if self._same_index(previous, current):
            return

        delegate.set_hovered_index(current)

        if previous.isValid():
            view.viewport().update(view.visualRect(previous))
        if current.isValid():
            view.viewport().update(view.visualRect(current))
        if not current.isValid():
            view.viewport().update()

    def _update_menu_hover(self, event: QMouseEvent) -> None:
        menu = self._tracked_menu
        if menu is None or not menu.isVisible():
            return

        local = menu.mapFromGlobal(event.globalPosition().toPoint())
        action = menu.actionAt(local) if menu.rect().contains(local) else None
        if action is not menu.activeAction():
            menu.setActiveAction(action)
            menu.update()

    def _handle_menu_lifecycle(self, event_type: QEvent.Type) -> None:
        menu = self._tracked_menu
        if menu is None:
            return
        if event_type in {
            QEvent.Type.Leave,
            QEvent.Type.HoverLeave,
            QEvent.Type.WindowDeactivate,
            QEvent.Type.Hide,
        }:
            menu.setActiveAction(None)
            menu.update()
        if event_type in {QEvent.Type.Hide, QEvent.Type.Destroy}:
            self._tracked_menu = None

    def _handle_view_lifecycle(self, event_type: QEvent.Type) -> None:
        if event_type in {
            QEvent.Type.WindowDeactivate,
            QEvent.Type.Hide,
        }:
            self._set_view_hover(QModelIndex())
        if event_type in {QEvent.Type.Hide, QEvent.Type.Destroy}:
            self._restore_item_view()

    def _restore_item_view(self) -> None:
        view = self._tracked_view
        original = self._original_delegate
        if view is not None:
            try:
                view.viewport().removeEventFilter(self)
            except RuntimeError:
                pass
            if original is not None:
                view.setItemDelegate(original)
            view.viewport().update()

        self._tracked_view = None
        self._original_delegate = None
        self._hover_delegate = None

    @staticmethod
    def _same_index(left: QModelIndex, right: QModelIndex) -> bool:
        return (
            left.isValid() == right.isValid()
            and (
                not left.isValid()
                or (
                    left.model() is right.model()
                    and left.row() == right.row()
                    and left.column() == right.column()
                    and left.parent() == right.parent()
                )
            )
        )
