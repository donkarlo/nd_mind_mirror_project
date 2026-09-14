"""Background QRunnable for one TikZ Visual preview render."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRunnable
from PySide6.QtGui import QImage

from nd_mind_mirror.graphic.tikz.bridge.renderer import TikZRenderer


class TikZVisualPreviewRenderTask(QRunnable):
    """Render one TikZ source away from the Qt GUI thread."""

    def __init__(
        self,
        *,
        renderer: TikZRenderer,
        source: str,
        target: Path,
        cache_key: tuple[Path, int, int],
        referring_file: Path,
        raw_input: str,
        completion: Callable[
            [tuple[Path, int, int], Path, str, QImage | None, str | None],
            None,
        ],
    ) -> None:
        super().__init__()
        self._renderer = renderer
        self._source = source
        self._target = target
        self._cache_key = cache_key
        self._referring_file = referring_file
        self._raw_input = raw_input
        self._completion = completion

    def run(self) -> None:
        try:
            result = self._renderer.render(self._source, self._target)
            image = QImage.fromData(base64.b64decode(result.png_base64))
            if image.isNull():
                raise RuntimeError("TikZ preview renderer returned an empty image")
            self._completion(
                self._cache_key,
                self._referring_file,
                self._raw_input,
                image,
                None,
            )
        except Exception as exc:
            self._completion(
                self._cache_key,
                self._referring_file,
                self._raw_input,
                None,
                str(exc),
            )
