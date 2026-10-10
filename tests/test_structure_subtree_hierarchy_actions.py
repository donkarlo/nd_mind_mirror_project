"""Regression coverage for semantic Structure promotion and demotion."""

from nd_mind_mirror.core.latex.structure.latex_structure_level_planner import (
    LatexStructureLevelPlanner,
)
from nd_mind_mirror.core.latex.structure.latex_structure_parser import (
    LatexStructureParser,
)


SOURCE = (
    r"\documentclass{article}" "\n"
    r"\begin{document}" "\n"
    r"\section{Root}" "\n"
    r"\subsection{Branch}" "\n"
    r"\subsubsection{Child}" "\n"
    r"\paragraph{Grandchild}" "\n"
    "some text\n"
    r"\section{Unchanged}" "\n"
    r"\subsection{Sibling}" "\n"
    r"\end{document}" "\n"
)


def _node(structure, title):
    return next(item for item in structure if item.title == title)


def test_increase_hierarchy_promotes_complete_branch_one_level() -> None:
    structure = LatexStructureParser().parse(SOURCE)
    branch = _node(structure, "Branch")
    result = LatexStructureLevelPlanner().change(
        SOURCE, structure, branch.source_position, -1,
    )
    assert result is not None
    new_source, focus_line = result
    assert r"\section{Branch}" in new_source
    assert r"\subsection{Child}" in new_source
    assert r"\subsubsection{Grandchild}" in new_source
    assert r"\section{Unchanged}" in new_source
    assert r"\subsection{Sibling}" in new_source
    assert focus_line == branch.line_number


def test_decrease_hierarchy_demotes_complete_branch_one_level() -> None:
    structure = LatexStructureParser().parse(SOURCE)
    branch = _node(structure, "Branch")
    result = LatexStructureLevelPlanner().change(
        SOURCE, structure, branch.source_position, 1,
    )
    assert result is not None
    new_source, _ = result
    assert r"\subsubsection{Branch}" in new_source
    assert r"\paragraph{Child}" in new_source
    assert r"\subparagraph{Grandchild}" in new_source
    assert r"\section{Unchanged}" in new_source


def test_reject_boundary_and_nonheading_without_touching_source() -> None:
    source = SOURCE.replace(r"\section{Root}", r"\part{Root}")
    structure = LatexStructureParser().parse(source)
    root = _node(structure, "Root")
    deep = _node(structure, "Grandchild")
    planner = LatexStructureLevelPlanner()
    assert planner.change(source, structure, root.source_position, -1) is None
    assert planner.change(source, structure, deep.source_position, 1) is not None
    source = source.replace(r"\paragraph{Grandchild}", r"\subparagraph{Grandchild}")
    structure = LatexStructureParser().parse(source)
    assert planner.change(source, structure, _node(structure, "Grandchild").source_position, 1) is None


def test_starred_titles_preserve_stars_and_leave_comments_untouched() -> None:
    source = (
        r"\documentclass{article}" "\n"
        r"\section{A}" "\n"
        "% \\subsection{Comment}\n"
        r"\subsection*{B}" "\n"
        r"\subsubsection{C}" "\n"
    )
    structure = LatexStructureParser().parse(source)
    result = LatexStructureLevelPlanner().change(
        source, structure, _node(structure, "B").source_position, -1,
    )
    assert result is not None
    rewritten, _ = result
    assert r"\section*{B}" in rewritten
    assert r"\subsection{C}" in rewritten
    assert "% \\subsection{Comment}" in rewritten
