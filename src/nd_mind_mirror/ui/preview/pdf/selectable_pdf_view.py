from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtQuickWidgets import QQuickWidget


class SelectablePdfView(QQuickWidget):
    _MIN_ZOOM = 0.20
    _MAX_ZOOM = 8.00
    _ZOOM_STEP = 1.15

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._reload_token = 0
        self._pan_token = 0
        self._is_panning = False
        self._pan_last_position = None
        self.setResizeMode(
            QQuickWidget.ResizeMode.SizeRootObjectToView
        )
        qml_path = Path(__file__).with_name(
            "selectable_pdf_view.qml"
        )
        self.setSource(
            QUrl.fromLocalFile(str(qml_path))
        )

    def wheelEvent(self, event: QWheelEvent) -> None:
        if bool(
            event.modifiers()
            & Qt.KeyboardModifier.ControlModifier
        ):
            delta = event.angleDelta().y()
            if delta == 0:
                delta = event.pixelDelta().y()

            if delta == 0:
                event.accept()
                return

            root = self.rootObject()
            if root is None:
                event.accept()
                return

            try:
                current = float(root.property("zoomScale"))
            except (TypeError, ValueError):
                current = 1.0

            if current <= 0:
                current = 1.0

            # A conventional wheel notch is 120 angle units. Keep the
            # change proportional so high-resolution wheels and touchpads
            # still feel smooth.
            if event.angleDelta().y() != 0:
                steps = delta / 120.0
                factor = self._ZOOM_STEP ** steps
            else:
                factor = (
                    self._ZOOM_STEP
                    if delta > 0
                    else 1.0 / self._ZOOM_STEP
                )

            zoom = max(
                self._MIN_ZOOM,
                min(current * factor, self._MAX_ZOOM),
            )
            root.setProperty("zoomScale", zoom)
            event.accept()
            return

        super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        middle_pan = (
            event.button()
            == Qt.MouseButton.MiddleButton
        )
        control_left_pan = (
            event.button()
            == Qt.MouseButton.LeftButton
            and bool(
                event.modifiers()
                & Qt.KeyboardModifier.ControlModifier
            )
        )

        if middle_pan or control_left_pan:
            self._is_panning = True
            self._pan_last_position = event.position()
            self.grabMouse()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._is_panning
            and self._pan_last_position is not None
        ):
            position = event.position()
            delta = position - self._pan_last_position
            self._pan_last_position = position

            root = self.rootObject()
            if root is not None:
                # Drag the document as if it were a sheet of paper: moving
                # the mouse right/down moves the visible content right/down,
                # which means the scroll offsets move left/up.
                root.setProperty(
                    "panDeltaX",
                    float(-delta.x()),
                )
                root.setProperty(
                    "panDeltaY",
                    float(-delta.y()),
                )
                self._pan_token += 1
                root.setProperty(
                    "panToken",
                    self._pan_token,
                )

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._is_panning:
            if event.button() in {
                Qt.MouseButton.MiddleButton,
                Qt.MouseButton.LeftButton,
            }:
                self._is_panning = False
                self._pan_last_position = None
                self.releaseMouse()
                self.unsetCursor()
                event.accept()
                return

        super().mouseReleaseEvent(event)

    def show_pdf(
        self,
        path: str | Path,
        reset_position: bool = False,
    ) -> bool:
        if self.status() == QQuickWidget.Status.Error:
            return False

        root = self.rootObject()
        if root is None:
            return False

        root.setProperty(
            "resetPositionOnReload",
            bool(reset_position),
        )
        root.setProperty(
            "source",
            QUrl.fromLocalFile(
                str(Path(path).resolve())
            ),
        )
        # Qt Quick PDF can cache an unchanged source URL, so force an
        # explicit document reload for each newly rendered preview.
        self._reload_token += 1
        root.setProperty(
            "reloadToken",
            self._reload_token,
        )
        return True
