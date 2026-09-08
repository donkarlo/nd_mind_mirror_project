from PySide6.QtGui import QWheelEvent

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

    def _synchronize_qml_zoom_limit(self) -> None:
        root = self.rootObject()
        if root is None:
            return
        root.setProperty("maxSafeZoomScale", self._MAX_ZOOM)
