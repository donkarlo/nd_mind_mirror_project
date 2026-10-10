"""Fuzzy Structure navigation and deep heading definitions used in research."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nd_mind_mirror.core.latex.structure.latex_structure_parser import LatexStructureParser
from nd_mind_mirror.core.latex.structure.latex_structure_title_matcher import (
    LatexStructureTitleMatcher,
)
from nd_mind_mirror.ui.panel.structure.latex_structure_panel import LatexStructurePanel


APP = QApplication.instance() or QApplication([])


DEEP_SOURCE = (
    "\\documentclass{article}\n"
    "\\begin{document}\n"
    "\\section{Cognitive Architecture}\n"
    "\\DeepSection{4}{Predictive Processing}\n"
    "\\DeepSection{5}{Active Inference}\n"
    "\\ndsectionsix{Homeostatic Balance}\n"
    "\\subsubsubsubsubsubsection{Precision Estimation}\n"
    "\\includegraphics{graph.png}\n"
    "\\section{Unrelated Topic}\n"
    "\\end{document}\n"
)


def test_deep_heading_source_parser_recognizes_all_supported_syntaxes() -> None:
    structure = LatexStructureParser().parse(DEEP_SOURCE)
    assert [(item.kind, item.level) for item in structure if item.kind != "image"] == [
        ("section", 2),
        ("DeepSection:4", 5),
        ("DeepSection:5", 6),
        ("ndsectionsix", 7),
        ("subsubsubsubsubsubsection", 8),
        ("section", 2),
    ]
    assert structure[-2].title == "graph.png"
    assert structure[-2].level == 9
    assert structure[-2].parent_source_position == structure[-3].source_position
    assert structure[-1].parent_source_position is None


def test_deep_heading_parser_ignores_invalid_macros_and_comments() -> None:
    source = (
        "% \\DeepSection{6}{Commented}\n"
        "\\DeepSection{11}{Invalid}\n"
        "\\DeepSection{word}{Invalid}\n"
        "\\DeepSection{10}{Last supported}\n"
        "\\subsubsubsubsubsubsubsubsubsection{Deep alias}\n"
    )
    assert [(entry.kind, entry.title) for entry in LatexStructureParser().parse(source)] == [
        ("DeepSection:10", "Last supported"),
        ("subsubsubsubsubsubsubsubsubsection", "Deep alias"),
    ]


def test_typo_tolerant_matcher_handles_phrases_and_persian() -> None:
    assert LatexStructureTitleMatcher.matches("Predictive Processing", "predicitve procesing")
    assert LatexStructureTitleMatcher.matches("Homeostatic Balance", "homeostatic balnce")
    assert LatexStructureTitleMatcher.matches("پیش‌بینی پردازش", "پیش بینی")
    assert LatexStructureTitleMatcher.matches("راه خانه", "راه خنه")
    assert LatexStructureTitleMatcher.matches("آن زن", "آن زان")
    assert not LatexStructureTitleMatcher.matches("Cognitive Architecture", "unrelated")
    assert not LatexStructureTitleMatcher.matches("Active Inference", "zz")


def test_structure_search_preserves_ancestors_and_restores_tree(tmp_path: Path) -> None:
    panel = LatexStructurePanel()
    try:
        panel.set_document(tmp_path / "deep.tex", DEEP_SOURCE, immediate=True)
        assert panel._tree.topLevelItemCount() == 2
        root = panel._tree.topLevelItem(0)
        unrelated = panel._tree.topLevelItem(1)
        assert root.childCount() == 1
        root.setExpanded(False)
        panel._filter_input.setText("presicion estimaton")
        panel._filter_timer.stop()
        panel._apply_title_filter()
        assert not root.isHidden()
        assert root.isExpanded()
        assert unrelated.isHidden()
        matching = [
            item for item in panel._all_items_in_source_order()
            if "Precision Estimation" in item.text(0)
        ]
        assert len(matching) == 1 and not matching[0].isHidden()
        assert root.child(0).isExpanded()
        panel._filter_input.clear()
        assert not root.isHidden()
        assert not unrelated.isHidden()
        assert not root.isExpanded()
    finally:
        panel.close()


def test_structure_search_enter_navigates_to_matching_deep_title(tmp_path: Path) -> None:
    panel = LatexStructurePanel()
    try:
        panel.set_document(tmp_path / "deep.tex", DEEP_SOURCE, immediate=True)
        visited = []
        panel.line_activated.connect(visited.append)
        panel._filter_input.setText("homeostatic balnce")
        panel._activate_first_filter_match()
        assert visited == [6]
    finally:
        panel.close()


def test_structure_detects_custom_heading_edits_for_rescan(tmp_path: Path) -> None:
    panel = LatexStructurePanel()
    try:
        source = "\\section{A}\n\\DeepSection{9}{Old title}\n"
        updated = source.replace("Old title", "New title")
        assert panel._structure_change_requires_rescan(source, updated)
        assert panel._signature_for(tmp_path / "deep.tex", source) != panel._signature_for(
            tmp_path / "deep.tex", updated,
        )
    finally:
        panel.close()
