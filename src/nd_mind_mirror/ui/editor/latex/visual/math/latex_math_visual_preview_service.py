"""Synchronous cached math service for Visual LaTeX mode."""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from .latex_display_math_extractor import LatexDisplayMathExtractor
from .latex_inline_math_extractor import LatexInlineMathExtractor
from .latex_math_batch_renderer import LatexMathBatchRenderer
from .latex_math_image_size_policy import LatexMathImageSizePolicy
from .latex_math_renderer import LatexMathRenderer


class LatexMathVisualPreviewService(QObject):
    """Prepare inline and display formulas before Visual projection is built."""

    preview_ready = Signal(str, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._display_extractor = LatexDisplayMathExtractor()
        self._inline_extractor = LatexInlineMathExtractor()
        self._batch_renderer = LatexMathBatchRenderer()
        self._single_renderer = LatexMathRenderer()
        self._size_policy = LatexMathImageSizePolicy(parent)
        self._cache: dict[str, QImage] = {}

    @classmethod
    def is_inline_math(cls, raw: str) -> bool:
        text = str(raw).strip()
        return (
            len(text) >= 2 and text.startswith("$") and text.endswith("$")
        ) or (text.startswith(r"\(") and text.endswith(r"\)"))

    @classmethod
    def is_display_math(cls, raw: str) -> bool:
        text = str(raw).strip()
        if text.startswith(r"\[") and text.endswith(r"\]"):
            return True
        environments = (
            "equation",
            "equation*",
            "align",
            "align*",
            "gather",
            "gather*",
            "multline",
            "multline*",
        )
        return any(text.startswith(f"\\begin{{{name}}}") for name in environments)

    @classmethod
    def is_math(cls, raw: str) -> bool:
        return cls.is_inline_math(raw) or cls.is_display_math(raw)

    def preload_display_math(self, source: str) -> int:
        """Preload every unique inline and display formula with one TeX batch."""
        formulas = self._all_formulas(str(source))
        missing = [raw for raw in formulas if raw not in self._cache]
        if not missing:
            return 0

        try:
            rendered = self._batch_renderer.render(missing)
        except Exception as exc:
            self._log_failure("batch", exc)
            return 0

        count = 0
        for raw in missing:
            image = rendered.get(raw)
            if image is None or image.isNull():
                continue
            self._cache[raw] = self._size_policy.prepare(
                raw,
                image,
                display=self.is_display_math(raw),
            )
            count += 1

        if count:
            inline_count = sum(
                1
                for raw in missing
                if raw in self._cache and self.is_inline_math(raw)
            )
            display_count = sum(
                1
                for raw in missing
                if raw in self._cache and self.is_display_math(raw)
            )
            print(
                "[visual-math] rendered "
                f"{count} formulas in one batch "
                f"({inline_count} inline, {display_count} display)",
                file=sys.stderr,
                flush=True,
            )
        return count

    def request(self, raw: str) -> QImage | None:
        """Return cached math immediately, with a late fallback for display math."""
        key = str(raw).strip()
        if not key:
            return None

        cached = self._cache.get(key)
        if cached is not None and not cached.isNull():
            return QImage(cached)

        if self.is_inline_math(key):
            return None
        if not self.is_display_math(key):
            return None

        try:
            image = self._single_renderer.render(key)
        except Exception as exc:
            self._log_failure("single", exc)
            return None

        self._cache[key] = self._size_policy.prepare(
            key,
            image,
            display=True,
        )
        print(
            "[visual-math] rendered 1 late display formula",
            file=sys.stderr,
            flush=True,
        )
        return QImage(self._cache[key])

    def logical_size(
        self,
        raw: str,
        image: QImage,
        *,
        display: bool,
    ) -> tuple[float, float]:
        """Return DPI-independent logical dimensions for QTextImageFormat."""
        return self._size_policy.logical_size(
            raw,
            image,
            display=display,
        )

    def _all_formulas(self, source: str) -> list[str]:
        formulas: list[str] = []
        seen: set[str] = set()
        for raw in (
            *self._inline_extractor.extract(source),
            *self._display_extractor.extract(source),
        ):
            key = str(raw).strip()
            if key and key not in seen:
                seen.add(key)
                formulas.append(key)
        return formulas

    @staticmethod
    def _log_failure(stage: str, error: Exception) -> None:
        detail = " ".join(str(error).splitlines()[-10:])
        print(
            f"[visual-math] {stage} failed: {detail}",
            file=sys.stderr,
            flush=True,
        )
