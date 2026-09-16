"""Batch-render display mathematics with one LuaLaTeX process and QtPdf."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument


class LatexMathBatchRenderer:
    """Render many display formulas in one TeX compilation.

    Each formula is wrapped in its own ``preview`` environment.  The preview
    package therefore emits one tight PDF page per formula, and QtPdf converts
    those pages directly to QImage objects without matplotlib or pdftocairo.
    """

    def __init__(self, *, raster_scale: float = 2.6, max_dimension: int = 2600) -> None:
        self._raster_scale = max(float(raster_scale), 1.0)
        self._max_dimension = max(int(max_dimension), 400)

    def render(self, formulas: list[str]) -> dict[str, QImage]:
        ordered = [str(formula).strip() for formula in formulas if str(formula).strip()]
        if not ordered:
            return {}

        lualatex = shutil.which("lualatex")
        if not lualatex:
            raise RuntimeError("lualatex was not found on PATH")

        with tempfile.TemporaryDirectory(prefix="nd_visual_math_batch_") as temporary:
            directory = Path(temporary)
            tex_path = directory / "formulas.tex"
            pdf_path = directory / "formulas.pdf"
            tex_path.write_text(self._document(ordered), encoding="utf-8")

            process = subprocess.run(
                [
                    lualatex,
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-file-line-error",
                    str(tex_path),
                ],
                cwd=directory,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=30,
                check=False,
            )
            if process.returncode != 0 or not pdf_path.is_file():
                raise RuntimeError(self._tail(process.stdout or ""))

            document = QPdfDocument()
            load_error = document.load(str(pdf_path))
            if load_error != QPdfDocument.Error.None_:
                raise RuntimeError(f"QtPdf could not load math batch PDF: {load_error}")

            page_count = document.pageCount()
            if page_count != len(ordered):
                raise RuntimeError(
                    "Visual math batch page mismatch: "
                    f"expected {len(ordered)}, got {page_count}"
                )

            rendered: dict[str, QImage] = {}
            for page_index, raw in enumerate(ordered):
                point_size = document.pagePointSize(page_index)
                width = max(int(round(point_size.width() * self._raster_scale)), 1)
                height = max(int(round(point_size.height() * self._raster_scale)), 1)
                largest = max(width, height)
                if largest > self._max_dimension:
                    factor = self._max_dimension / float(largest)
                    width = max(int(round(width * factor)), 1)
                    height = max(int(round(height * factor)), 1)

                image = document.render(page_index, QSize(width, height))
                if image.isNull():
                    raise RuntimeError(f"QtPdf returned an empty image for formula {page_index + 1}")
                rendered[raw] = QImage(image)

            document.close()
            return rendered

    @staticmethod
    def _document(formulas: list[str]) -> str:
        previews = "\n".join(
            "\\begin{preview}\n"
            f"{formula}\n"
            "\\end{preview}"
            for formula in formulas
        )
        return (
            "\\documentclass{article}\n"
            "\\usepackage{amsmath,amssymb,mathtools}\n"
            "\\usepackage[active,tightpage]{preview}\n"
            "\\PreviewBorder=3pt\n"
            "\\pagestyle{empty}\n"
            "\\begin{document}\n"
            f"{previews}\n"
            "\\end{document}\n"
        )

    @staticmethod
    def _tail(log: str, count: int = 30) -> str:
        lines = [line for line in str(log).splitlines() if line.strip()]
        return "\n".join(lines[-count:]) or "Visual math batch compilation failed"
