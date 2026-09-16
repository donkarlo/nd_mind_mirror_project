"""Single-formula facade over the Visual math batch renderer."""

from __future__ import annotations

from PySide6.QtGui import QImage

from .latex_math_batch_renderer import LatexMathBatchRenderer


class LatexMathRenderer:
    """Render one display formula without matplotlib or external PDF converters."""

    def __init__(self) -> None:
        self._batch_renderer = LatexMathBatchRenderer()

    def render(self, raw: str) -> QImage:
        key = str(raw).strip()
        if not key:
            raise ValueError("Empty LaTeX math")
        rendered = self._batch_renderer.render([key])
        image = rendered.get(key)
        if image is None or image.isNull():
            raise RuntimeError("Visual math renderer returned no image")
        return QImage(image)
