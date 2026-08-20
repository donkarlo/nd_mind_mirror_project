from pathlib import Path

from nd_mind_mirror.core.latex.input.recursive.recursive_input_resolver import (
    RecursiveInputResolver,
)


def test_complete_input_keeps_its_section_level(tmp_path: Path) -> None:
    master = tmp_path / "master.tex"
    child = tmp_path / "language.tex"

    master.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Neural circuits}\n"
        "\\input{language}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    child.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Language}\n"
        "Text.\n"
        "\\subsection{Syntax}\n"
        "More.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )

    rendered = RecursiveInputResolver().resolve(master.read_text(), master)

    assert "\\section{Language}" in rendered
    assert "\\subsection{Language}" not in rendered
    assert "\\subsection{Syntax}" in rendered


def test_complete_input_title_only_becomes_sibling_section(tmp_path: Path) -> None:
    master = tmp_path / "master.tex"
    child = tmp_path / "language.tex"

    master.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Neuron types}\n"
        "\\input{language}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    child.write_text(
        "\\documentclass{article}\n"
        "\\title{Language}\n"
        "\\author{Someone}\n"
        "\\begin{document}\n"
        "\\maketitle\n"
        "Language body.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )

    rendered = RecursiveInputResolver().resolve(master.read_text(), master)

    assert "\\section{Neuron types}" in rendered
    assert "\\section{Language}" in rendered
    assert "\\subsection{Language}" not in rendered
    assert "Language body." in rendered


def test_input_child_root_is_sibling_of_include_site(tmp_path: Path) -> None:
    master = tmp_path / "master.tex"
    child = tmp_path / "details.tex"

    master.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Data flow}\n"
        "\\input{details}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    child.write_text(
        "\\subsection{Included root}\n"
        "\\subsubsection{Included child}\n",
        encoding="utf-8",
    )

    rendered = RecursiveInputResolver().resolve(master.read_text(), master)

    assert "\\section{Included root}" in rendered
    assert "\\subsection{Included child}" in rendered
