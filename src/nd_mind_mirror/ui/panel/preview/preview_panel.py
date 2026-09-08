from nd_mind_mirror.ui.panel.preview.preview_panel_base import (
    PreviewPanel as BasePreviewPanel,
)


class PreviewPanel(BasePreviewPanel):
    _MIN_ZOOM_PERCENT = 20
    _MAX_ZOOM_PERCENT = 2000

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._zoom_edit.setToolTip(
            "PDF zoom percentage (20% to 2000%)"
        )

    def _apply_zoom_edit(self) -> None:
        text = self._zoom_edit.text().strip().rstrip("%").strip()
        try:
            percent = int(round(float(text)))
        except ValueError:
            percent = 100
        percent = max(
            self._MIN_ZOOM_PERCENT,
            min(percent, self._MAX_ZOOM_PERCENT),
        )
        self._zoom_edit.setText(f"{percent}%")
        self._preview.set_zoom_percent(percent)
