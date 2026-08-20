from pathlib import Path

from nd_mind_mirror.core.render.latex.latex_preview_source_builder import LatexPreviewSourceBuilder


def _builder() -> LatexPreviewSourceBuilder:
    root = Path(__file__).resolve().parents[1]
    return LatexPreviewSourceBuilder(root / "resources" / "latex_preview_template.tex")


def test_multiple_complete_documents_preview_most_substantial_document() -> None:
    source = r'''\documentclass{article}
\begin{document}
\maketitle
\end{document}

\documentclass{article}
\usepackage{amsmath}
\begin{document}
This is the intended second document with real content.
\end{document}
'''
    prepared = _builder().build(source)
    assert prepared.count(r"\documentclass") == 1
    assert "intended second document" in prepared
    assert prepared.count("\n") >= source[: source.rfind(r"\documentclass")].count("\n")


def test_preview_qml_clamps_fit_and_reload_zoom() -> None:
    root = Path(__file__).resolve().parents[1]
    qml = (root / "src/nd_mind_mirror/ui/preview/pdf/selectable_pdf_view.qml").read_text()
    assert "property real maxSafeZoomScale: 5.00" in qml
    assert "pdfView.renderScale = root.safeScale(root.fitTargetWidth / effectiveWidthPoints)" in qml
    assert "pdfView.renderScale = root.safeScale(pdfView.renderScale)" in qml


def test_sparse_content_fit_falls_back_to_page_width() -> None:
    root = Path(__file__).resolve().parents[1]
    code = (root / "src/nd_mind_mirror/ui/preview/pdf/selectable_pdf_view.py").read_text()
    assert "_MIN_CONTENT_FIT_FRACTION = 0.20" in code
    assert "content_width_points = 0.0" in code
