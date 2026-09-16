"""Presentation sizing policy for rendered Visual-mode mathematics."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


class LatexMathImageSizePolicy:
    """Normalize display-math image size to the Visual editor's typography."""

    _MULTIROW_ENVIRONMENT = re.compile(
        r"\\begin\{(?:align\*?|gather\*?|multline\*?|cases)\}"
    )
    _ROW_BREAK = re.compile(r"\\\\(?:\[[^\]]*\])?")

    def __init__(self, editor) -> None:
        self._editor = editor

    def prepare(self, raw: str, image: QImage, *, display: bool) -> QImage:
        if image.isNull() or not display:
            return QImage(image)

        font_height = self._font_height()
        rows = self._visual_row_count(str(raw))
        target_height = font_height * 1.30 * rows
        natural_height = max(float(image.height()), 1.0)
        scale = max(1.0, min(target_height / natural_height, 5.0))

        target_width = max(int(round(float(image.width()) * scale)), 1)
        target_pixel_height = max(int(round(natural_height * scale)), 1)
        available = self._available_width()
        if target_width > available:
            width_scale = available / float(target_width)
            target_width = available
            target_pixel_height = max(int(round(target_pixel_height * width_scale)), 1)

        if target_width == image.width() and target_pixel_height == image.height():
            return QImage(image)
        return image.scaled(
            target_width,
            target_pixel_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _font_height(self) -> float:
        try:
            return max(float(self._editor.fontMetrics().height()), 14.0)
        except (AttributeError, RuntimeError):
            return 22.0

    def _available_width(self) -> int:
        try:
            return max(int(self._editor.viewport().width()) - 110, 220)
        except (AttributeError, RuntimeError):
            return 1200

    @classmethod
    def _visual_row_count(cls, raw: str) -> int:
        if cls._MULTIROW_ENVIRONMENT.search(raw) is None:
            return 1
        return max(len(cls._ROW_BREAK.findall(raw)) + 1, 1)
