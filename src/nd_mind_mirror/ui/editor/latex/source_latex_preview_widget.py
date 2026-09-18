"""Overlay widget for one rendered LaTeX Source preview."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel


class SourceLatexPreviewWidget(QLabel):
    """Show a cached render without becoming part of canonical source text."""

    def __init__(self, parent=None) -> None:
        """Initialize a transparent non-interactive overlay preview label."""
        super().__init__(parent)
        self._cache_key: tuple[int, int] | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            "QLabel { background: #ffffff; border: 1px solid #d6d9dd; "
            "border-radius: 3px; padding: 2px; }"
        )
        self.hide()

    def display_image(
        self,
        image: QImage,
        *,
        target_width: int,
        x: int,
        y: int,
    ) -> bool:
        """Display one preview image at a target width and viewport position."""
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
