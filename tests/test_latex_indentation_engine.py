from nd_mind_mirror.core.latex.indentation.latex_indentation_engine import (
    LatexIndentationEngine,
)


def test_enter_after_item_continues_same_list_level() -> None:
    source = (
        "\\begin{document}\n"
        "    \\begin{itemize}\n"
        "        \\item first item\n"
        "    \\end{itemize}\n"
        "\\end{document}\n"
    )
    position = source.index("first item") + len("first item")
    engine = LatexIndentationEngine(indent_size=4)

    assert engine.list_item_continuation(source, position) == "        \\item "


def test_enter_after_nested_item_keeps_nested_item_indent() -> None:
    source = (
        "\\begin{document}\n"
        "    \\begin{itemize}\n"
        "        \\item parent\n"
        "        \\begin{enumerate}\n"
        "            \\item child\n"
        "        \\end{enumerate}\n"
        "    \\end{itemize}\n"
        "\\end{document}\n"
    )
    position = source.index("child") + len("child")
    engine = LatexIndentationEngine(indent_size=4)

    assert engine.list_item_continuation(source, position) == "            \\item "


def test_plain_line_does_not_create_item() -> None:
    source = (
        "\\begin{document}\n"
        "    \\begin{itemize}\n"
        "        ordinary prose\n"
        "    \\end{itemize}\n"
        "\\end{document}\n"
    )
    position = source.index("ordinary prose") + len("ordinary prose")
    engine = LatexIndentationEngine(indent_size=4)

    assert engine.list_item_continuation(source, position) is None
