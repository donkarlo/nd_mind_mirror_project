"""QTreeWidget dedicated to semantic LaTeX Structure drag/drop requests."""

from PySide6.QtCore import QByteArray, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QMouseEvent
from PySide6.QtWidgets import QApplication, QAbstractItemView, QTreeWidget


class LatexStructureTree(QTreeWidget):
    """Emit semantic Structure drops without mutating tree rows directly."""

    structure_drop_requested = Signal(int, int, str)

    _SOURCE_POSITION_ROLE = Qt.ItemDataRole.UserRole + 1
    _KIND_ROLE = Qt.ItemDataRole.UserRole + 3
    _MIME_TYPE = "application/x-nd-mind-mirror-latex-structure-node"
    _HEADING_KINDS = {
        "part",
        "chapter",
        "section",
        "subsection",
        "subsubsection",
        "paragraph",
        "subparagraph",
    }

    def __init__(self, parent=None) -> None:
        """Configure a tree whose drag gesture is independent of Qt selection state."""
        super().__init__(parent)
        self._drag_origin: QPoint | None = None
        self._pressed_source_position: int | None = None

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Remember the pressed row before semantic highlighting clears selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            point = event.position().toPoint()
            self._drag_origin = point
            self._pressed_source_position = self._source_position(self.itemAt(point))
        else:
            self._clear_drag_origin()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Start a real Qt drag once the platform drag threshold is crossed."""
        if (
            self._drag_origin is None
            or self._pressed_source_position is None
            or not (event.buttons() & Qt.MouseButton.LeftButton)
        ):
            super().mouseMoveEvent(event)
            return

        distance = (event.position().toPoint() - self._drag_origin).manhattanLength()
        if distance < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        item = self.itemAt(self._drag_origin)
        source_position = self._pressed_source_position
        if item is None or source_position is None:
            self._clear_drag_origin()
            super().mouseMoveEvent(event)
            return

        # Preserve Qt's native item MIME data so its own drop indicator is the
        # single visual source of truth for before/inside/after placement.
        mime_data = self.mimeData([item])
        mime_data.setData(
            self._MIME_TYPE,
            QByteArray(str(source_position).encode("ascii")),
        )
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        self._clear_drag_origin()
        drag.exec(Qt.DropAction.MoveAction)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Clear an unfinished drag origin after an ordinary click/release."""
        self._clear_drag_origin()
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event) -> None:
        """Accept only semantic drags that originated from this Structure tree."""
        if self._is_own_structure_drag(event):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        """Let Qt calculate and paint the canonical drop indicator position."""
        if not self._is_own_structure_drag(event):
            super().dragMoveEvent(event)
            return

        event.setDropAction(Qt.DropAction.MoveAction)
        super().dragMoveEvent(event)
        if not event.isAccepted():
            event.accept()

    def dropEvent(self, event) -> None:
        """Convert Qt's painted drop indicator into one semantic move request."""
        if not self._is_own_structure_drag(event):
            super().dropEvent(event)
            return

        source_position = self._source_position_from_mime(event.mimeData())
        if source_position is None:
            event.ignore()
            return

        source_item = self._item_for_source_position(source_position)
        point = event.position().toPoint()
        target = self.itemAt(point)
        placement = self._placement_from_qt_indicator(target)

        if placement == "end":
            self.structure_drop_requested.emit(source_position, -1, "end")
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return

        target_position = self._source_position(target)
        if target_position is None or target_position == source_position:
            event.ignore()
            return

        if not self._drop_shape_is_representable(source_item, target, placement):
            event.ignore()
            return

        self.structure_drop_requested.emit(
            source_position,
            target_position,
            placement,
        )
        # The LaTeX source owns the mutation. Never invoke QTreeWidget.dropEvent,
        # because doing so would move UI rows independently from canonical text.
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def _placement_from_qt_indicator(self, target) -> str:
        """Map the exact indicator Qt painted to the semantic placement."""
        position = self.dropIndicatorPosition()
        if (
            target is None
            or position == QAbstractItemView.DropIndicatorPosition.OnViewport
        ):
            return "end"
        if position == QAbstractItemView.DropIndicatorPosition.AboveItem:
            return "before"
        if position == QAbstractItemView.DropIndicatorPosition.BelowItem:
            return "after"
        return "inside"

    def _drop_shape_is_representable(self, source_item, target_item, placement: str) -> bool:
        """Reject tree gestures that LaTeX cannot represent without side effects."""
        source_kind = self._kind(source_item)
        target_kind = self._kind(target_item)
        if placement == "inside":
            return target_kind in self._HEADING_KINDS
        if (
            source_kind in self._HEADING_KINDS
            and target_kind not in self._HEADING_KINDS
        ):
            return False
        return True

    def _item_for_source_position(self, source_position: int):
        """Find one UI row by the canonical source identity stored in its role."""
        wanted = int(source_position)

        def walk(item):
            if self._source_position(item) == wanted:
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(self.topLevelItemCount()):
            found = walk(self.topLevelItem(index))
            if found is not None:
                return found
        return None

    def _is_own_structure_drag(self, event) -> bool:
        """Return whether an event carries this tree's semantic drag payload."""
        return bool(
            event.source() is self
            and event.mimeData() is not None
            and event.mimeData().hasFormat(self._MIME_TYPE)
        )

    @classmethod
    def _source_position_from_mime(cls, mime_data) -> int | None:
        """Decode the canonical source position stored in the drag payload."""
        if mime_data is None or not mime_data.hasFormat(cls._MIME_TYPE):
            return None
        try:
            return int(bytes(mime_data.data(cls._MIME_TYPE)).decode("ascii"))
        except (TypeError, ValueError, UnicodeDecodeError):
            return None

    def _clear_drag_origin(self) -> None:
        """Forget transient pointer state after a click or completed drag."""
        self._drag_origin = None
        self._pressed_source_position = None

    @classmethod
    def _source_position(cls, item) -> int | None:
        """Return one tree item's canonical source offset."""
        if item is None:
            return None
        value = item.data(0, cls._SOURCE_POSITION_ROLE)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _kind(cls, item) -> str:
        if item is None:
            return ""
        return str(item.data(0, cls._KIND_ROLE) or "")
