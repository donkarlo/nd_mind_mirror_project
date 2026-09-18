"""Cached LuaLaTeX renderer for Source-mode formula and table previews."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument


class SourceLatexPreviewRenderer:
    """Render arbitrary supported snippets to tight in-memory images."""

    def __init__(self, *, raster_scale: float = 2.6, max_dimension: int = 2800) -> None:
        """Initialize rendering limits and the in-memory snippet cache."""
        self._raster_scale = max(float(raster_scale), 1.0)
        self._max_dimension = max(int(max_dimension), 400)
        self._cache: dict[str, QImage] = {}
        self._failed: set[str] = set()

    def render_many(self, snippets: list[str]) -> dict[str, QImage]:
        """Render uncached snippets and return valid cached images by snippet."""
        ordered: list[str] = []
        seen: set[str] = set()
        for snippet in snippets:
            raw = str(snippet).strip()
            if not raw or raw in seen:
                continue
            seen.add(raw)
            if raw not in self._cache and raw not in self._failed:
                ordered.append(raw)

        if ordered:
            try:
                self._cache.update(self._render_batch(ordered))
            except Exception:
                # One unsupported snippet must not hide every other preview.
                for raw in ordered:
                    try:
                        self._cache.update(self._render_batch([raw]))
                    except Exception:
                        self._failed.add(raw)

        return {
            raw: QImage(self._cache[raw])
            for raw in seen
            if raw in self._cache and not self._cache[raw].isNull()
        }

    def _render_batch(self, snippets: list[str]) -> dict[str, QImage]:
        """Compile one batch of snippets and rasterize each tight PDF page."""
        lualatex = shutil.which("lualatex")
        if not lualatex:
            raise RuntimeError("lualatex was not found on PATH")

        with tempfile.TemporaryDirectory(prefix="nd_source_latex_preview_") as temporary:
            directory = Path(temporary)
            tex_path = directory / "previews.tex"
            pdf_path = directory / "previews.pdf"
            tex_path.write_text(self._document(snippets), encoding="utf-8")
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
                raise RuntimeError(f"QtPdf could not load Source preview PDF: {load_error}")
            if document.pageCount() != len(snippets):
                raise RuntimeError(
                    "Source preview page mismatch: "
                    f"expected {len(snippets)}, got {document.pageCount()}"
                )

            result: dict[str, QImage] = {}
            for page_index, raw in enumerate(snippets):
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
                    raise RuntimeError(f"QtPdf returned an empty Source preview image for page {page_index + 1}")
                result[raw] = QImage(image)
            document.close()
            return result

    @staticmethod
    def _document(snippets: list[str]) -> str:
        """Build the temporary standalone LaTeX document for a preview batch."""
        previews = "\n".join(
            "\\begin{preview}\n"
            f"{snippet}\n"
            "\\end{preview}"
            for snippet in snippets
        )
        return (
            "\\documentclass{article}\n"
            "\\usepackage{amsmath,amssymb,mathtools}\n"
            "\\usepackage{array,booktabs,multirow,tabularx}\n"
            "\\usepackage{xcolor}\n"
            "\\usepackage[active,tightpage]{preview}\n"
            "\\PreviewBorder=3pt\n"
            "\\pagestyle{empty}\n"
            "\\begin{document}\n"
            f"{previews}\n"
            "\\end{document}\n"
        )

    @staticmethod
    def _tail(log: str, count: int = 24) -> str:
        """Return a compact tail of compiler output for diagnostics."""
        lines = [line for line in str(log).splitlines() if line.strip()]
        return "\n".join(lines[-count:]) or "Source LaTeX preview compilation failed"
