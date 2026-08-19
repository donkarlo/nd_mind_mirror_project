from nd_mind_mirror.core.latex.structure.latex_structure_parser import (
    LatexStructureParser,
)


def test_structure_parser_extracts_hierarchy_and_line_numbers() -> None:
    source = (
        "\\part{P}\n"
        "\\chapter{C}\n"
        "\\section{S}\n"
        "text\n"
        "\\subsection{SS}\n"
        "\\subsubsection{SSS}\n"
    )

    items = LatexStructureParser().parse(source)

    assert [(item.kind, item.title, item.line_number) for item in items] == [
        ("part", "P", 1),
        ("chapter", "C", 2),
        ("section", "S", 3),
        ("subsection", "SS", 5),
        ("subsubsection", "SSS", 6),
    ]


def test_structure_parser_prefers_short_title_for_pandoc_style_heading() -> None:
    source = (
        "\\section[اکنون ]"
        "{\\texorpdfstring{\\protect\\hypertarget{anchor}{}{}اکنون }{اکنون }}\n"
    )

    items = LatexStructureParser().parse(source)

    assert len(items) == 1
    assert items[0].kind == "section"
    assert items[0].title == "اکنون"


def test_structure_parser_ignores_comments_and_literal_environments() -> None:
    source = (
        "% \\section{commented}\n"
        "\\begin{verbatim}\n"
        "\\section{literal}\n"
        "\\end{verbatim}\n"
        "\\section{real}\n"
    )

    items = LatexStructureParser().parse(source)

    assert [(item.kind, item.title) for item in items] == [("section", "real")]
