from nd_mind_mirror.core.latex.structure.latex_structure_move_planner import (
    LatexStructureMovePlanner,
)
from nd_mind_mirror.core.latex.structure.latex_structure_parser import (
    LatexStructureParser,
)


def _item(items, kind: str, title: str):
    return next(item for item in items if item.kind == kind and item.title == title)


def test_parser_assigns_explicit_parents_and_sibling_indexes() -> None:
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{A}\n"
        "\\begin{figure}\n"
        "\\includegraphics{a.png}\n"
        "\\end{figure}\n"
        "\\subsection{A1}\n"
        "\\begin{table}\n"
        "\\caption{T}\n"
        "\\begin{tabular}{c}x\\end{tabular}\n"
        "\\end{table}\n"
        "\\section{B}\n"
        "\\end{document}\n"
    )

    items = LatexStructureParser().parse(source)
    section_a = _item(items, "section", "A")
    figure = _item(items, "image", "a.png")
    subsection = _item(items, "subsection", "A1")
    table = _item(items, "table", "T")
    section_b = _item(items, "section", "B")

    assert section_a.parent_source_position is None
    assert section_a.level == 2
    assert section_a.sibling_index == 0
    assert figure.parent_source_position == section_a.source_position
    assert figure.level == 7
    assert figure.sibling_index == 0
    assert subsection.parent_source_position == section_a.source_position
    assert subsection.level == 3
    assert subsection.sibling_index == 1
    assert table.parent_source_position == subsection.source_position
    assert table.level == 7
    assert section_b.parent_source_position is None
    assert section_b.level == 2
    assert section_b.sibling_index == 1


def test_section_dropped_inside_section_becomes_subsection_with_subtree() -> None:
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{A}\n"
        "A\n"
        "\\section{B}\n"
        "\\subsection{B1}\n"
        "B\n"
        "\\section{C}\n"
        "\\end{document}\n"
    )
    parser = LatexStructureParser()
    items = parser.parse(source)
    section_a = _item(items, "section", "A")
    section_b = _item(items, "section", "B")

    result = LatexStructureMovePlanner().move(
        source,
        items,
        section_b.source_position,
        section_a.source_position,
        "inside",
    )

    assert result is not None
    rewritten, _ = result
    assert "\\subsection{B}" in rewritten
    assert "\\subsubsection{B1}" in rewritten
    reparsed = parser.parse(rewritten)
    moved = _item(reparsed, "subsection", "B")
    assert moved.parent_source_position == _item(reparsed, "section", "A").source_position


def test_article_part_child_never_turns_into_undefined_chapter() -> None:
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Root}\n"
        "\\part{P}\n"
        "\\section{A}\n"
        "\\end{document}\n"
    )
    parser = LatexStructureParser()
    items = parser.parse(source)
    part = _item(items, "part", "P")
    root_section = _item(items, "section", "Root")

    result = LatexStructureMovePlanner().move(
        source,
        items,
        root_section.source_position,
        part.source_position,
        "inside",
    )

    assert result is not None
    rewritten, _ = result
    assert "\\chapter{Root}" not in rewritten
    assert "\\section{Root}" in rewritten


def test_deepest_heading_reparent_is_rejected_instead_of_clamped() -> None:
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{A}\n"
        "\\subsection{B}\n"
        "\\subsubsection{C}\n"
        "\\paragraph{D}\n"
        "\\subparagraph{E}\n"
        "\\section{F}\n"
        "\\end{document}\n"
    )
    items = LatexStructureParser().parse(source)
    deepest = _item(items, "subparagraph", "E")
    section_f = _item(items, "section", "F")

    result = LatexStructureMovePlanner().move(
        source,
        items,
        section_f.source_position,
        deepest.source_position,
        "inside",
    )

    assert result is None


def test_heading_beside_leaf_is_rejected_to_prevent_hidden_reparenting() -> None:
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{A}\n"
        "\\begin{figure}\n"
        "\\includegraphics{a.png}\n"
        "\\end{figure}\n"
        "\\section{B}\n"
        "\\end{document}\n"
    )
    items = LatexStructureParser().parse(source)
    figure = _item(items, "image", "a.png")
    section_b = _item(items, "section", "B")

    planner = LatexStructureMovePlanner()
    assert planner.move(
        source,
        items,
        section_b.source_position,
        figure.source_position,
        "before",
    ) is None
    assert planner.move(
        source,
        items,
        section_b.source_position,
        figure.source_position,
        "after",
    ) is None


def test_leaf_dropped_inside_heading_stays_direct_child() -> None:
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{A}\n"
        "\\subsection{A1}\n"
        "text\n"
        "\\section{B}\n"
        "\\begin{figure}\n"
        "\\includegraphics{b.png}\n"
        "\\end{figure}\n"
        "\\end{document}\n"
    )
    parser = LatexStructureParser()
    items = parser.parse(source)
    section_a = _item(items, "section", "A")
    figure = _item(items, "image", "b.png")

    result = LatexStructureMovePlanner().move(
        source,
        items,
        figure.source_position,
        section_a.source_position,
        "inside",
    )

    assert result is not None
    rewritten, _ = result
    reparsed = parser.parse(rewritten)
    moved = _item(reparsed, "image", "b.png")
    new_a = _item(reparsed, "section", "A")
    new_a1 = _item(reparsed, "subsection", "A1")
    assert moved.parent_source_position == new_a.source_position
    assert moved.source_position < new_a1.source_position


def test_subsection_dropped_on_empty_viewport_is_promoted_to_root_level() -> None:
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{A}\n"
        "\\subsection{A1}\n"
        "body\n"
        "\\section{B}\n"
        "\\end{document}\n"
    )
    parser = LatexStructureParser()
    items = parser.parse(source)
    subsection = _item(items, "subsection", "A1")

    result = LatexStructureMovePlanner().move(
        source,
        items,
        subsection.source_position,
        -1,
        "end",
    )

    assert result is not None
    rewritten, _ = result
    assert "\\section{A1}" in rewritten
    reparsed = parser.parse(rewritten)
    moved = _item(reparsed, "section", "A1")
    assert moved.parent_source_position is None


def test_reparent_preserves_skipped_heading_depth_by_relative_shift() -> None:
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Parent}\n"
        "\\section{Moved}\n"
        "\\paragraph{Direct paragraph}\n"
        "text\n"
        "\\section{Tail}\n"
        "\\end{document}\n"
    )
    parser = LatexStructureParser()
    items = parser.parse(source)
    parent = _item(items, "section", "Parent")
    moved = _item(items, "section", "Moved")

    result = LatexStructureMovePlanner().move(
        source,
        items,
        moved.source_position,
        parent.source_position,
        "inside",
    )

    assert result is not None
    rewritten, _ = result
    assert "\\subsection{Moved}" in rewritten
    assert "\\subparagraph{Direct paragraph}" in rewritten
    assert "\\subsubsection{Direct paragraph}" not in rewritten


def test_neural_architecture_anatomy_subtree_shifts_one_heading_level() -> None:
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Nervous system}\n"
        "text\n"
        "\\section{Anatomy of a neuron}\n"
        "\\subsection{Graded potentials}\n"
        "\\subsection{Anatomy of action potentials}\n"
        "\\subsection{Converting evidence probability distributions to EPSP and IPSP}\n"
        "\\subsubsection{Simulation with Frequency-Modulated Mobius}\n"
        "\\section{Neuron types}\n"
        "\\end{document}\n"
    )
    parser = LatexStructureParser()
    items = parser.parse(source)
    parent = _item(items, "section", "Nervous system")
    moved = _item(items, "section", "Anatomy of a neuron")

    result = LatexStructureMovePlanner().move(
        source,
        items,
        moved.source_position,
        parent.source_position,
        "inside",
    )

    assert result is not None
    rewritten, _ = result
    assert "\\subsection{Anatomy of a neuron}" in rewritten
    assert "\\subsubsection{Graded potentials}" in rewritten
    assert "\\subsubsection{Anatomy of action potentials}" in rewritten
    assert "\\paragraph{Simulation with Frequency-Modulated Mobius}" in rewritten


def test_neural_architecture_mixed_paragraph_and_subsection_shift_safely() -> None:
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Nervous system}\n"
        "\\section{Different types of potential summation in a destination neuron}\n"
        "\\paragraph{Spatial summation}\n"
        "\\paragraph{Temporal summation}\n"
        "\\subsection{Population coding}\n"
        "\\section{Neural circuits and the whole architecture together}\n"
        "\\end{document}\n"
    )
    parser = LatexStructureParser()
    items = parser.parse(source)
    parent = _item(items, "section", "Nervous system")
    moved = _item(
        items,
        "section",
        "Different types of potential summation in a destination neuron",
    )

    result = LatexStructureMovePlanner().move(
        source,
        items,
        moved.source_position,
        parent.source_position,
        "inside",
    )

    assert result is not None
    rewritten, _ = result
    assert "\\subsection{Different types of potential summation" in rewritten
    assert "\\subparagraph{Spatial summation}" in rewritten
    assert "\\subparagraph{Temporal summation}" in rewritten
    assert "\\subsubsection{Population coding}" in rewritten


def test_leaf_level_can_never_capture_a_later_deeper_heading_in_tree_renderer() -> None:
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{A}\n"
        "\\begin{figure}\n"
        "\\includegraphics{a.png}\n"
        "\\end{figure}\n"
        "\\paragraph{P}\n"
        "text\n"
        "\\section{B}\n"
        "\\end{document}\n"
    )
    items = LatexStructureParser().parse(source)
    section = _item(items, "section", "A")
    figure = _item(items, "image", "a.png")
    paragraph = _item(items, "paragraph", "P")

    assert figure.parent_source_position == section.source_position
    assert paragraph.parent_source_position == section.source_position
    assert figure.level > paragraph.level
