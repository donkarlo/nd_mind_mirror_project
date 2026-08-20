from pathlib import Path

from nd_mind_mirror.core.render.latex.latex_preview_source_builder import (
    LatexPreviewSourceBuilder,
)


def _builder(tmp_path: Path) -> LatexPreviewSourceBuilder:
    article = tmp_path / "article.tex"
    article.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "% ND_MIND_MIRROR_CONTENT\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    beamer = tmp_path / "beamer.tex"
    beamer.write_text(
        "\\documentclass{beamer}\n"
        "\\begin{document}\n"
        "% ND_MIND_MIRROR_CONTENT\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    return LatexPreviewSourceBuilder(article, beamer)


def test_persian_fragment_gets_preview_only_babel_support(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    result = builder.build("این یک متن فارسی است و Transformer هم دارد.")

    assert r"\usepackage[provide=*,bidi=basic]{babel}" in result
    assert r"\babelprovide[import,main]{persian}" in result
    assert r"\babelfont{rm}{FreeSerif}" in result
    assert "این یک متن فارسی است" in result


def test_english_fragment_does_not_load_persian_support(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    result = builder.build("This is English prose.")

    assert r"\babelprovide[import,main]{persian}" not in result


def test_existing_persian_babel_setup_is_not_duplicated(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    source = (
        "\\documentclass{article}\n"
        "\\usepackage[provide=*,bidi=basic]{babel}\n"
        "\\babelprovide[import,main]{persian}\n"
        "\\babelfont{rm}{FreeSerif}\n"
        "\\begin{document}\n"
        "متن فارسی\n"
        "\\end{document}\n"
    )

    result = builder.build(source)

    assert result == source


def test_existing_polyglossia_persian_setup_is_not_mixed_with_babel(
    tmp_path: Path,
) -> None:
    builder = _builder(tmp_path)
    source = (
        "\\documentclass[16pt,a4paper]{extarticle}\n"
        "\\usepackage{fontspec}\n"
        "\\usepackage{polyglossia}\n"
        "\\setmainlanguage[numerals=eastern]{persian}\n"
        "\\setotherlanguage{english}\n"
        "\\setmainfont[Script=Arabic]{Amiri}\n"
        "\\begin{document}\n"
        "متن فارسی\n"
        "\\end{document}\n"
    )

    result = builder.build(source)

    assert result == source
    assert r"\babelprovide" not in result


def test_algorithm_environments_get_preview_only_packages(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    source = (
        "\\documentclass{beamer}\n"
        "\\begin{document}\n"
        "\\begin{frame}\n"
        "\\begin{algorithm}[H]\n"
        "\\begin{algorithmic}[1]\n"
        "\\State Test\n"
        "\\end{algorithmic}\n"
        "\\end{algorithm}\n"
        "\\end{frame}\n"
        "\\end{document}\n"
    )

    result = builder.build(source)

    assert r"\usepackage{algorithm}" in result
    assert r"\usepackage{algpseudocode}" in result


def test_toolbar_colorbox_gets_preview_only_xcolor(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\colorbox{yellow!20}{highlighted}\n"
        "\\end{document}\n"
    )

    result = builder.build(source)

    assert r"\usepackage{xcolor}" in result

def test_preview_repairs_colorbox_hidden_by_comment(tmp_path: Path) -> None:
    template = tmp_path / "template.tex"
    template.write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "% ND_MIND_MIRROR_CONTENT\n\\end{document}\n",
        encoding="utf-8",
    )
    builder = LatexPreviewSourceBuilder(template)
    source = (
        "\\documentclass{article}\n"
        "\\usepackage{xcolor}\n"
        "\\begin{document}\n"
        "\\colorbox{yellow!20}{hello % comment\n"
        "\\end{document}\n"
    )
    rendered = builder.build(source)
    assert "\\colorbox{yellow!20}{hello }% comment" in rendered



def test_chapter_fragment_uses_report_preview_class(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    source = (
        "\\chapter{Virtual environment}\n"
        "\\section{Virtual environment}\n"
        "\\begin{minted}{bash}\n"
        "source ~/phd-venv/bin/activate\n"
        "\\end{minted}\n"
    )

    result = builder.build(source)

    assert r"\documentclass{report}" in result
    assert r"\chapter{Virtual environment}" in result


def test_section_only_fragment_keeps_article_preview_class(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    result = builder.build("\\section{Only a section}\n")

    assert r"\documentclass{article}" in result
    assert r"\documentclass{report}" not in result


def test_includegraphics_gets_preview_only_graphicx(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\includegraphics[width=.9\\linewidth]{graphics/graphic.png}\n"
        "\\end{document}\n"
    )
    result = builder.build(source)
    assert r"\usepackage{graphicx}" in result
