"""Provide a real horizontal scrollbar for long Navigator paths."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTreeView


class NavigatorHorizontalScrollController(QObject):
    """Keep Navigator names unelided and widen column zero to its visible content."""

    _CONFIGURED_PROPERTY = "nd_navigator_horizontal_scroll_configured"

    def eventFilter(self, watched, event) -> bool:
        if not isinstance(watched, QTreeView) or not self._is_navigator_tree(watched):
            return False

        if event.type() in {QEvent.Type.Polish, QEvent.Type.Show}:
            self._configure_tree(watched)
        elif event.type() in {QEvent.Type.Resize, QEvent.Type.LayoutRequest}:
            if bool(watched.property(self._CONFIGURED_PROPERTY)):
                self._schedule_width_refresh(watched)
        return False

    def _configure_tree(self, tree: QTreeView) -> None:
        if bool(tree.property(self._CONFIGURED_PROPERTY)):
            self._schedule_width_refresh(tree)
            return

        tree.setProperty(self._CONFIGURED_PROPERTY, True)
        tree.setTextElideMode(Qt.TextElideMode.ElideNone)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        tree.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        header = tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)

        tree.expanded.connect(lambda _index, item=tree: self._schedule_width_refresh(item))
        tree.collapsed.connect(lambda _index, item=tree: self._schedule_width_refresh(item))
        model = tree.model()
        if model is not None:
            try:
                model.rowsInserted.connect(
                    lambda *_args, item=tree: self._schedule_width_refresh(item)
                )
                model.layoutChanged.connect(
                    lambda *_args, item=tree: self._schedule_width_refresh(item)
                )
            except (AttributeError, RuntimeError, TypeError):
                pass
        self._schedule_width_refresh(tree)

    @staticmethod
    def _is_navigator_tree(tree: QTreeView) -> bool:
        parent = tree.parent()
        while parent is not None:
            if parent.__class__.__name__ == "FileSystemPanel":
                return True
            parent = parent.parent()
        return False

    @staticmethod
    def _schedule_width_refresh(tree: QTreeView) -> None:
        QTimer.singleShot(0, lambda item=tree: NavigatorHorizontalScrollController._refresh_width(item))

    @staticmethod
    def _refresh_width(tree: QTreeView) -> None:
        try:
            viewport_width = max(int(tree.viewport().width()), 1)
            content_width = max(int(tree.sizeHintForColumn(0)), 1)
            width = max(viewport_width, content_width + 36)
            tree.header().resizeSection(0, width)
        except RuntimeError:
            pass
