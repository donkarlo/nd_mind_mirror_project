"""Logical presentation sizing for rendered Visual-mode mathematics."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


class LatexMathImageSizePolicy:
    """Map high-resolution math rasters to readable QTextDocument dimensions."""

    _MULTIROW_ENVIRONMENT = re.compile(
        r"\\begin\{(?:align\*?|gather\*?|multline\*?|cases)\}"
    )
    _ROW_BREAK = re.compile(r"\\\\(?:\[[^\]]*\])?")
    _TALL_EXPRESSION = re.compile(
        r"\\(?:d?frac|sqrt|sum|prod|int|left|right|Big|big)"
    )

    def __init__(self, editor) -> None:
        self._editor = editor

    def prepare(self, raw: str, image: QImage, *, display: bool) -> QImage:
        """Return a raster whose native size is already readable by QTextDocument.

        The Visual editor historically inserted display-math images at their native
        raster dimensions.  Keep inline math high-resolution for its own insertion
        policy, but normalize display math here so even callers that do not apply
        ``logical_size`` cannot collapse a standalone formula to a few pixels.
        """
        if image.isNull() or not display:
            return QImage(image)

        width, height = self.logical_size(raw, image, display=True)
        target_width = max(int(round(width)), 1)
        target_height = max(int(round(height)), 1)
        if image.width() == target_width and image.height() == target_height:
            return QImage(image)
        return image.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def logical_size(
        self,
        raw: str,
        image: QImage,
        *,
        display: bool,
    ) -> tuple[float, float]:
        """Return width/height in Visual-document pixels, independent of raster DPI."""
        if image.isNull():
            return 1.0, 1.0

        line_height = self._font_height()
        if display:
            rows = self._visual_row_count(str(raw))
            if rows > 1:
                target_height = max(
                    line_height * 1.65 * rows,
                    line_height * 2.35,
                    48.0,
                )
            elif self._TALL_EXPRESSION.search(str(raw)) is not None:
                target_height = max(line_height * 2.65, 52.0)
            else:
                target_height = max(line_height * 2.05, 42.0)
            available = self._available_width()
        else:
            target_height = max(line_height * 1.08, 18.0)
            available = max(self._available_width(), 80)

        ratio = float(image.width()) / max(float(image.height()), 1.0)
        width = max(target_height * ratio, 1.0)
        height = target_height

        if width > float(available):
            scale = float(available) / width
            width = float(available)
            height = max(height * scale, 1.0)

        return width, height

    def _font_height(self) -> float:
        try:
            return max(float(self._editor.fontMetrics().height()), 18.0)
        except (AttributeError, RuntimeError):
            return 24.0

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
