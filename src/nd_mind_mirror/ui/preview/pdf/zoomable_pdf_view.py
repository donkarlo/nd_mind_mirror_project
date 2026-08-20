from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtPdfWidgets import QPdfView


class ZoomablePdfView(QPdfView):
    _MIN_ZOOM = 0.20
    _MAX_ZOOM = 5.00
    _ZOOM_STEP = 1.15

    def wheelEvent(self, event: QWheelEvent) -> None:
        if bool(
            event.modifiers()
            & Qt.KeyboardModifier.ControlModifier
        ):
            direction = event.angleDelta().y()

            if direction == 0:
                event.accept()
                return

            current = self.zoomFactor()

            if current <= 0:
                current = 1.0

            factor = (
                current * self._ZOOM_STEP
                if direction > 0
                else current / self._ZOOM_STEP
            )
            factor = max(
                self._MIN_ZOOM,
                min(factor, self._MAX_ZOOM),
            )

            self.setZoomMode(
                QPdfView.ZoomMode.Custom
            )
            self.setZoomFactor(factor)
            event.accept()
            return

        super().wheelEvent(event)
