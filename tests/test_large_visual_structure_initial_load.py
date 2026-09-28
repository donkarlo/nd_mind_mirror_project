"""Regression coverage for first-load Structure on virtualized LaTeX files."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.ui.editor.bookmark.selection_large_latex_editor import (
    SelectionLargeLatexEditor,
)
from nd_mind_mirror.ui.panel.structure.latex_structure_panel import (
    LatexStructurePanel,
)


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _large_source() -> str:
    middle = "Ordinary prose for the large document.\n" * 4500
    return (
        "\\section{First}\n"
        + middle
        + "\\section{Middle}\n"
        + middle
        + "\\section{Last}\n"
    )
def test_visual_restore_keeps_complete_canonical_source(tmp_path: Path) -> None:
    app = _application()
    source = _large_source()
    path = tmp_path / "large.tex"
    editor = SelectionLargeLatexEditor(
        completions=[],
        source_path=path,
        app_settings=YamlSettings(),
    )
    editor.set_content(source)
    assert editor.source_is_windowed
    assert len(editor.document().toPlainText()) < len(source)

    emitted: list[str] = []
    editor.content_changed.connect(emitted.append)
    editor.restore_view_state(
        {
            "edit_mode": "visual",
            "active_source_line": 1,
            "active_source_column": 1,
            "visible_source_line": 1,
            "visible_source_column": 1,
            "cursor_position": 0,
            "anchor_position": 0,
            "vertical_scroll": 0,
            "horizontal_scroll": 0,
        }
    )
    app.processEvents()

    assert editor.edit_mode == "visual"
    assert editor.canonical_source() == source
    assert editor._visual_source_cache == source
    assert not editor.document().isModified()

    editor._flush_content()
    assert emitted[-1] == source
    assert editor.canonical_source() == source

    structure = LatexStructurePanel()
    structure.set_document(path, emitted[-1], immediate=True)
    app.processEvents()
    worker = structure._latex_worker
    assert worker is not None
    assert worker.wait(5000)
    app.processEvents()

    assert [node.title for node in structure._structure] == [
        "First",
        "Middle",
        "Last",
    ]

    structure.deleteLater()
    editor.deleteLater()
    app.processEvents()
