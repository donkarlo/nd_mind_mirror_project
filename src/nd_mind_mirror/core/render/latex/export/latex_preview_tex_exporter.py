from pathlib import Path

from nd_mind_mirror.core.render.latex.latex_renderer_base import LatexRenderer


class LatexPreviewTexExporter:
    """Export the exact prepared LaTeX source behind a visible Preview PDF."""

    def __init__(self, renderer: LatexRenderer) -> None:
        self._renderer = renderer

    def export_for_pdf(
        self,
        *,
        pdf_path: str | Path,
        destination_path: str | Path,
    ) -> Path:
        prepared = self._renderer.prepared_source_for_pdf(pdf_path)
        if prepared is None:
            raise ValueError(
                "The LaTeX source for the currently visible Preview PDF is "
                "not available."
            )

        destination = Path(destination_path).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(prepared, encoding="utf-8")
        return destination
