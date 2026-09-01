"""Small non-editing raster preview used beside visible LaTeX source code."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel


class SourceGraphicPreviewWidget(QLabel):
    """Display one cached source image without modifying the QTextDocument."""

    _MAX_HEIGHT = 150

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cache_key: tuple[str, int, int, int] | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "QLabel { background: #ffffff; border: 1px solid #cfd4da; "
            "border-radius: 3px; padding: 2px; }"
        )
        self.hide()

    def display_image(
        self,
        image_path: Path,
        target_width: int,
        y: int,
        lane_left: int,
        lane_width: int,
    ) -> bool:
        """Show image_path in the reserved source-preview lane and preserve aspect ratio."""
        try:
            stat = image_path.stat()
        except OSError:
            self.hide()
            return False

        width = max(48, min(int(target_width), max(int(lane_width) - 12, 48)))
        cache_key = (str(image_path), int(stat.st_mtime_ns), int(stat.st_size), width)
        if cache_key != self._cache_key:
            pixmap = QPixmap(str(image_path))
            if pixmap.isNull():
                self.hide()
                self._cache_key = None
                return False
            scaled = pixmap.scaled(
                width,
                self._MAX_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)
            self.resize(scaled.width() + 6, scaled.height() + 6)
            self._cache_key = cache_key

        x = int(lane_left) + max((int(lane_width) - self.width()) // 2, 0)
        self.move(x, max(int(y), 0))
        self.show()
        self.raise_()
        return True
