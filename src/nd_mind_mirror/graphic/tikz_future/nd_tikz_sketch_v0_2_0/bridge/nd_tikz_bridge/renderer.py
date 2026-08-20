from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import base64
import os
import shutil
import subprocess
import tempfile


DEFAULT_LIBRARIES = "arrows.meta,positioning,calc,fit,shapes.geometric"


@dataclass(frozen=True)
class RenderResult:
    png_base64: str
    log: str


class TikZRenderer:
    def __init__(
        self,
        workspace: Path,
        preamble_path: Path | None = None,
        shell_escape: bool = False,
    ) -> None:
        self.workspace = workspace.expanduser().resolve()
        self.preamble_path = preamble_path.expanduser().resolve() if preamble_path else None
        self.shell_escape = shell_escape

    def render(self, source: str, source_file: Path) -> RenderResult:
        lualatex = shutil.which("lualatex")
        converter = shutil.which("pdftocairo") or shutil.which("pdftoppm")
        if not lualatex:
            raise RuntimeError("lualatex was not found on PATH")
        if not converter:
            raise RuntimeError("pdftocairo/pdftoppm was not found on PATH")

        with tempfile.TemporaryDirectory(prefix="nd_tikz_bridge_") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            tex_path = temp_dir / "diagram.tex"
            tex_path.write_text(self._preview_document(source), encoding="utf-8")
            env = os.environ.copy()
            existing = env.get("TEXINPUTS", "")
            texinputs = [str(source_file.parent), f"{self.workspace}//"]
            if existing:
                texinputs.append(existing)
            env["TEXINPUTS"] = os.pathsep.join(texinputs) + os.pathsep

            command = [
                lualatex,
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
            ]
            if self.shell_escape:
                command.append("-shell-escape")
            command.append(str(tex_path))
            process = subprocess.run(
                command,
                cwd=temp_dir,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=45,
                check=False,
            )
            log = process.stdout or ""
            pdf_path = temp_dir / "diagram.pdf"
            if process.returncode != 0 or not pdf_path.exists():
                raise RuntimeError(self._last_log_lines(log))

            png_path = temp_dir / "diagram.png"
            if Path(converter).name == "pdftocairo":
                convert = [converter, "-png", "-singlefile", "-r", "144", str(pdf_path), str(temp_dir / "diagram")]
            else:
                convert = [converter, "-png", "-singlefile", "-r", "144", str(pdf_path), str(temp_dir / "diagram")]
            converted = subprocess.run(
                convert,
                cwd=temp_dir,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=30,
                check=False,
            )
            if converted.returncode != 0 or not png_path.exists():
                raise RuntimeError(converted.stdout or "PDF to PNG conversion failed")

            encoded = base64.b64encode(png_path.read_bytes()).decode("ascii")
            return RenderResult(png_base64=encoded, log=log)

    def _preview_document(self, source: str) -> str:
        if "\\documentclass" in source:
            return source

        preamble = ""
        if self.preamble_path and self.preamble_path.is_file():
            preamble = self.preamble_path.read_text(encoding="utf-8") + "\n"

        body = self._with_render_canvas(source)

        return (
            "\\documentclass[tikz,border=0pt]{standalone}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\usepackage{xcolor}\n"
            "\\usepackage{tikz}\n"
            f"\\usetikzlibrary{{{DEFAULT_LIBRARIES}}}\n"
            + preamble
            + "\\begin{document}\n"
            + body
            + "\\end{document}\n"
        )


    @staticmethod
    def _with_render_canvas(source: str) -> str:
        """Use a fixed 16×11 TikZ-unit canvas for Pencil coordinate mapping.

        This is render-only; the real TikZ source is never modified with the
        bounding-box helper. The iPad maps its white canvas to the same range.
        """
        marker = "\\path[use as bounding box] (0,0) rectangle (16,11);\n"
        begin = "\\begin{tikzpicture}"
        if begin in source:
            index = source.find(begin) + len(begin)
            return source[:index] + "\n" + marker + source[index:]
        return begin + "\n" + marker + source + "\n\\end{tikzpicture}\n"

    @staticmethod
    def _last_log_lines(log: str, count: int = 24) -> str:
        lines = [line for line in log.splitlines() if line.strip()]
        return "\n".join(lines[-count:]) or "LuaLaTeX failed"
