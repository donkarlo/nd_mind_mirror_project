"""Inline rendered TikZ image used by the LaTeX Source editor."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QMenu


class SourceTikZPreviewWidget(QLabel):
    """Display an inline render with a context menu targeting its source file."""

    edit_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cache_key: tuple[int, int] | None = None
        self._source_path: str | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet(
            "QLabel { background: #ffffff; border: 1px solid #cfd4da; "
            "border-radius: 3px; padding: 2px; }"
        )
        self.hide()

    def set_tikz_source(self, source_path: str | None) -> None:
        """Associate the visible render with its canonical editable source."""
        self._source_path = str(source_path) if source_path else None

    def contextMenuEvent(self, event) -> None:
        if not self._source_path:
            event.ignore()
            return
        menu = QMenu(self)
        edit = menu.addAction("Edit TikZ in iPad…")
        selected = menu.exec(event.globalPos())
        if selected == edit:
            self.edit_requested.emit(self._source_path)
        event.accept()

    def display_image(
        self,
        image: QImage,
        target_width: int,
        x: int,
        y: int,
    ) -> bool:
        """Show an in-memory render at target_width while preserving aspect ratio."""
        if image.isNull():
            self.hide()
            return False

        width = max(int(target_width), 1)
        cache_key = (int(image.cacheKey()), width)
        if cache_key != self._cache_key:
            pixmap = QPixmap.fromImage(image)
            if pixmap.isNull():
                self.hide()
                self._cache_key = None
                return False
            scaled = pixmap.scaledToWidth(
                width,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)
            self.resize(scaled.width() + 6, scaled.height() + 6)
            self._cache_key = cache_key

        self.move(int(x), int(y))
        self.show()
        self.raise_()
        return True
