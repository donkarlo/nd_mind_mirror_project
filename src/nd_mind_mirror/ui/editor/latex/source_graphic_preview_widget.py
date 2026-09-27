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
        self._image_path: Path | None = None
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
        *,
        image_signature: tuple[int, int] | None = None,
    ) -> bool:
        """Show one cached raster while keeping scroll-time widget work minimal."""
        image_path = Path(image_path).expanduser().resolve()
        self._image_path = image_path
        signature = image_signature or self._read_signature(image_path)
        if signature is None:
            self.hide()
            return False

        width = max(int(target_width), 1)
        cache_key = (str(image_path), int(signature[0]), int(signature[1]), width)
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

        target_x = int(x)
        target_y = int(y)
        if self.x() != target_x or self.y() != target_y:
            self.move(target_x, target_y)
        if not self.isVisible():
            self.show()
            self.raise_()
        return True

    @property
    def image_path(self) -> Path | None:
        """Return the raster currently represented by this visible preview."""
        return self._image_path

    @staticmethod
    def _read_signature(image_path: Path) -> tuple[int, int] | None:
        """Read one raster signature when a controller-side cached value is unavailable."""
        try:
            stat = image_path.stat()
        except OSError:
            return None
        return int(stat.st_mtime_ns), int(stat.st_size)
