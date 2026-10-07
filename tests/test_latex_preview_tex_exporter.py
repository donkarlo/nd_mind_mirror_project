"""Tests for exporting the exact LaTeX behind the visible Preview PDF."""

from pathlib import Path

from nd_mind_mirror.core.render.latex.export.latex_preview_tex_exporter import (
    LatexPreviewTexExporter,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREPARED = (
    "\\documentclass{article}\n"
    "\\begin{document}\n"
    "prepared\n"
    "\\end{document}\n"
)


class _RendererStub:
    def __init__(self, prepared: str | None = PREPARED) -> None:
        self.prepared = prepared
        self.calls: list[Path] = []

    def prepared_source_for_pdf(self, pdf_path: str | Path) -> str | None:
        resolved = Path(pdf_path).expanduser().resolve()
        self.calls.append(resolved)
        return self.prepared


def test_exporter_writes_source_for_visible_pdf(tmp_path: Path) -> None:
    renderer = _RendererStub()
    exporter = LatexPreviewTexExporter(renderer)  # type: ignore[arg-type]
    pdf_path = tmp_path / "published.pdf"
    destination = tmp_path / "journal_2026_preview.tex"

    exported = exporter.export_for_pdf(
        pdf_path=pdf_path,
        destination_path=destination,
    )

    assert exported == destination
    assert renderer.calls == [pdf_path.resolve()]
    assert destination.read_text(encoding="utf-8") == PREPARED
