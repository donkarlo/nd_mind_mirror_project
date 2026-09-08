from pathlib import Path

from nd_mind_mirror.core.render.latex.latex_preview_source_builder import LatexPreviewSourceBuilder


def _default_template_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "src"
        / "nd_mind_mirror"
        / "core"
        / "settings"
        / "defaults"
        / "templates"
        / "latex_preview_template.tex"
    )


def test_fragment_preview_uses_tight_content_page() -> None:
    builder = LatexPreviewSourceBuilder(_default_template_path())
    source = "\\begin{forest}\n[A]\n\\end{forest}\n"

    prepared = builder.build(source)

    assert "\\usepackage[active,tightpage]{preview}" in prepared
    assert "\\begin{preview}" in prepared
    assert source.strip() in prepared
    assert "\\end{preview}" in prepared
    assert "adjustbox" not in prepared


def test_standalone_document_preview_keeps_original_page_geometry() -> None:
    builder = LatexPreviewSourceBuilder(_default_template_path())
    source = (
        "\\documentclass[a4paper]{article}\n"
        "\\begin{document}\n"
        "Standalone content\n"
        "\\end{document}\n"
    )

    prepared = builder.build(source)

    assert "\\usepackage[active,tightpage]{preview}" not in prepared
    assert "\\begin{preview}" not in prepared
    assert "Standalone content" in prepared
