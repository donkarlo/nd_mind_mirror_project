"""Apply Structure drag/drop rewrites to the active canonical LaTeX editor."""

from pathlib import Path

from PySide6.QtCore import QObject

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor


class StructureSourceRewriteController(QObject):
    """Own the single write path from Structure drag/drop to the current editor."""

    def __init__(self, structure_panel, editor_panel, window, parent=None) -> None:
        super().__init__(parent)
        self._structure_panel = structure_panel
        self._editor_panel = editor_panel
        self._window = window
        self._structure_panel.source_rewrite_requested.connect(self._apply_rewrite)

    def _apply_rewrite(
        self,
        expected_source: str,
        rewritten_source: str,
        line_number: int,
    ) -> None:
        path = self._editor_panel.current_path()
        editor = self._editor_panel.current_editor()
        if path is None or not isinstance(editor, LatexEditor):
            return
        path = Path(path).expanduser().resolve(strict=False)
        if path.suffix.lower() != ".tex":
            return

        current_source = self._editor_panel.current_content()
        if current_source != expected_source:
            self._structure_panel.set_document(
                path,
                current_source,
                immediate=True,
            )
            self._window.statusBar().showMessage(
                "Structure changed while dragging; the tree was refreshed. Drag again.",
                3500,
            )
            return

        specialized = getattr(editor, "apply_structural_source", None)
        if callable(specialized):
            specialized(rewritten_source, line_number)
        else:
            editor.set_content(rewritten_source)
            editor.document().setModified(True)
            editor.go_to_line(max(int(line_number), 1), align_top=True)

        self._structure_panel.set_document(
            path,
            rewritten_source,
            immediate=True,
        )
