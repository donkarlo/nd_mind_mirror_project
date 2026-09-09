from PySide6.QtGui import QCloseEvent, QWheelEvent

from nd_mind_mirror.ui.preview.pdf.selectable_pdf_view_base import (
    SelectablePdfView as BaseSelectablePdfView,
)


class SelectablePdfView(BaseSelectablePdfView):
    _MAX_ZOOM = 20.00

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._synchronize_qml_zoom_limit()

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._synchronize_qml_zoom_limit()
        super().wheelEvent(event)

    def set_zoom_percent(self, percent: int | float) -> None:
        self._synchronize_qml_zoom_limit()
        super().set_zoom_percent(percent)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Release native PDF resources before Qt tears down the Quick scene."""
        if hasattr(self, "_status_timer"):
            self._status_timer.stop()
        if hasattr(self, "_fit_document"):
            try:
                self._fit_document.close()
            except Exception:
                pass
        super().closeEvent(event)

    def _synchronize_qml_zoom_limit(self) -> None:
        root = self.rootObject()
        if root is None:
            return
        root.setProperty("maxSafeZoomScale", self._MAX_ZOOM)
