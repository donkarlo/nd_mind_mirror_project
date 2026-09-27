"""Regression tests for Structure click navigation across source refreshes."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nd_mind_mirror.ui.panel.structure.latex_structure_panel import (
    LatexStructurePanel,
)


def _application() -> QApplication:
    """Return one Qt application for headless Structure tests."""
    return QApplication.instance() or QApplication([])


def test_nonstructural_edit_keeps_structure_rows_activatable(tmp_path: Path) -> None:
    """Typing ordinary text must not invalidate unchanged Structure row generations."""
    _application()
    panel = LatexStructurePanel()
    path = tmp_path / "small.tex"
    before = "\\section{One}\ntext\n\\section{Two}\nmore\n"
    after = "\\section{One}\ntexts\n\\section{Two}\nmore\n"

    panel.set_document(path, before, immediate=True)
    item = panel._all_items_in_source_order()[1]
    generation = panel._parse_generation
    seen: list[int] = []
    panel.line_activated.connect(seen.append)

    panel.set_document(path, after, immediate=False)
    panel._on_item_clicked(item, 0)

    assert panel._parse_generation == generation
    assert seen == [3]


def test_stale_structure_click_resolves_against_current_source(tmp_path: Path) -> None:
    """A stale visible row must navigate to its current line instead of dropping the click."""
    _application()
    panel = LatexStructurePanel()
    path = tmp_path / "stale.tex"
    source = "\\section{One}\ntext\n\\section{Two}\nmore\n"

    panel.set_document(path, source, immediate=True)
    item = panel._all_items_in_source_order()[1]
    panel._source = "\n" + source
    panel._parse_generation += 1
    panel._applied_generation = -1
    seen: list[int] = []
    panel.line_activated.connect(seen.append)

    panel._on_item_clicked(item, 0)

    assert seen == [4]
    assert panel._applied_generation == panel._parse_generation
