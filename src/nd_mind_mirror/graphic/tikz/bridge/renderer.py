"""Render canonical TikZ source to a fixed-coordinate PNG preview."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import base64
import os
import shutil
import subprocess
import tempfile

from nd_mind_mirror.core.render.latex.reference.latex_preview_reference_materializer import (
    LatexPreviewReferenceMaterializer,
)


DEFAULT_LIBRARIES = (
    "arrows.meta,positioning,calc,fit,shapes.geometric,graphs,graphdrawing"
)


@dataclass(frozen=True)
class TikZRenderResult:
    """Rendered preview payload returned to the iPad or Visual client."""

    png_base64: str
    log: str


class TikZRenderer:
    """Render TikZ fragments without mutating their canonical source."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.expanduser().resolve()
        self._materializer = LatexPreviewReferenceMaterializer(self.workspace)

    def render(self, source: str, source_file: Path) -> TikZRenderResult:
        """Render source with LuaLaTeX and return a PNG preview."""
        lualatex = shutil.which("lualatex")
        converter = shutil.which("pdftocairo") or shutil.which("pdftoppm")
        if not lualatex:
            raise RuntimeError("lualatex was not found on PATH")
        if not converter:
            raise RuntimeError("pdftocairo/pdftoppm was not found on PATH")

        materialized_source = self._materializer.materialize(source, source_file)

        with tempfile.TemporaryDirectory(
            prefix="nd_mind_mirror_tikz_"
        ) as raw_temp:
            temp = Path(raw_temp)
            tex_path = temp / "diagram.tex"
            tex_path.write_text(
                self._preview_document(materialized_source),
                encoding="utf-8",
            )

            env = os.environ.copy()
            existing = env.get("TEXINPUTS", "")
            texinputs = [str(source_file.parent)]
            if existing:
                texinputs.append(existing)
            env["TEXINPUTS"] = os.pathsep.join(texinputs) + os.pathsep

            try:
                process = subprocess.run(
                    [
                        lualatex,
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        "-file-line-error",
                        str(tex_path),
                    ],
                    cwd=temp,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=20,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"LuaLaTeX TikZ render timed out after {exc.timeout:g} seconds"
                ) from exc

            log = process.stdout or ""
            pdf_path = temp / "diagram.pdf"
            if process.returncode != 0 or not pdf_path.is_file():
                raise RuntimeError(self._last_log_lines(log))

            png_path = temp / "diagram.png"
            try:
                converted = subprocess.run(
                    [
                        converter,
                        "-png",
                        "-singlefile",
                        "-r",
                        "144",
                        str(pdf_path),
                        str(temp / "diagram"),
                    ],
                    cwd=temp,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=20,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"PDF-to-PNG TikZ conversion timed out after {exc.timeout:g} seconds"
                ) from exc

            if converted.returncode != 0 or not png_path.is_file():
                raise RuntimeError(
                    converted.stdout or "PDF to PNG conversion failed"
                )
            return TikZRenderResult(
                png_base64=base64.b64encode(
                    png_path.read_bytes()
                ).decode("ascii"),
                log=log,
            )

    @staticmethod
    def _preview_document(source: str) -> str:
        """Wrap fragments in standalone only for rendering, never for saving."""
        if "\\documentclass" in source:
            return source
        body = TikZRenderer._with_render_canvas(source)
        return (
            "\\documentclass[tikz,border=0pt]{standalone}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\usepackage{xcolor}\n"
            "\\usepackage{tikz}\n"
            f"\\usetikzlibrary{{{DEFAULT_LIBRARIES}}}\n"
            "\\begin{document}\n"
            + body
            + "\\end{document}\n"
        )

    @staticmethod
    def _with_render_canvas(source: str) -> str:
        """Give iPad and renderer the same 16x11 TikZ coordinate canvas."""
        marker = "\\path[use as bounding box] (0,0) rectangle (16,11);\n"
        begin = "\\begin{tikzpicture}"
        if begin in source:
            index = source.find(begin) + len(begin)
            return source[:index] + "\n" + marker + source[index:]
        return (
            begin
            + "\n"
            + marker
            + source
            + "\n\\end{tikzpicture}\n"
        )

    @staticmethod
    def _last_log_lines(log: str, count: int = 28) -> str:
        """Return the useful tail of a failed LaTeX render."""
        lines = [line for line in log.splitlines() if line.strip()]
        return "\n".join(lines[-count:]) or "LuaLaTeX failed"
