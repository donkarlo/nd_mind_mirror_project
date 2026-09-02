"""Non-editing raster preview displayed in reserved LaTeX Source figure space."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel


class SourceGraphicPreviewWidget(QLabel):
    """Draw one inline Source image at its requested LaTeX-relative width."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cache_key: tuple[str, int, int, int] | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            "QLabel { background: #ffffff; border: 1px solid #cfd4da; "
            "border-radius: 3px; padding: 2px; }"
        )
        self.hide()

    def display_image(
        self,
        image_path: Path,
        target_width: int,
        x: int,
        y: int,
    ) -> bool:
        """Show image_path at exactly target_width while preserving its aspect ratio."""
        try:
            stat = image_path.stat()
        except OSError:
            self.hide()
            return False

        width = max(int(target_width), 1)
        cache_key = (str(image_path), int(stat.st_mtime_ns), int(stat.st_size), width)
        if cache_key != self._cache_key:
            pixmap = QPixmap(str(image_path))
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
