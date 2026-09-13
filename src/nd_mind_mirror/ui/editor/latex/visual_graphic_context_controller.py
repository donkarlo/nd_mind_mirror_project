"""Normalize existing Visual graphic blocks before their context menu is built."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import _BlockMeta


class VisualGraphicContextController(QObject):
    """Make existing image blocks reliably identify themselves as graphics."""

    _INSTALLED_PROPERTY = "nd_visual_graphic_context_controller"

    def __init__(self, editor_panel, parent=None) -> None:
        super().__init__(parent)
        self._editor_panel = editor_panel
        self._editor_panel.current_document_changed.connect(
            lambda *_args: self._attach_current_editor()
        )
        self._editor_panel.current_view_changed.connect(
            lambda *_args: self._attach_current_editor()
        )
        QTimer.singleShot(0, self._attach_current_editor)

    def _attach_current_editor(self) -> None:
        editor = self._editor_panel.current_editor()
        if not isinstance(editor, LatexEditor):
            return
        visual = editor._visual_editor
        if bool(visual.property(self._INSTALLED_PROPERTY)):
            return
        visual.setProperty(self._INSTALLED_PROPERTY, True)
        visual.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.ContextMenu and bool(
            watched.property(self._INSTALLED_PROPERTY)
        ):
            cursor = watched.cursorForPosition(event.pos())
            block = cursor.block()
            block_data = block.userData()
            raw = str(getattr(block_data, "raw", "") or "")
            if "\\includegraphics" in raw or cursor.charFormat().isImageFormat():
                source_line = self._source_line_for_graphic(
                    watched,
                    cursor.position(),
                    block_data,
                )
                block.setUserData(
                    self._graphic_metadata(
                        block_data,
                        raw=raw,
                        source_line=source_line,
                    )
                )
        return super().eventFilter(watched, event)

    @staticmethod
    def _source_line_for_graphic(watched, position: int, block_data) -> int:
        """Preserve an existing source line, or recover it from the Visual mapping."""
        try:
            source_line = int(getattr(block_data, "source_line", 0) or 0)
        except (TypeError, ValueError):
            source_line = 0
        if source_line > 0:
            return source_line

        resolver = getattr(watched, "source_location_for_position", None)
        if not callable(resolver):
            return 0
        try:
            line, _column = resolver(position)
            return max(int(line), 0)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return 0

    @staticmethod
    def _graphic_metadata(block_data, *, raw: str, source_line: int) -> _BlockMeta:
        """Return the exact metadata type expected by the Visual context menu."""
        if isinstance(block_data, _BlockMeta):
            block_data.kind = "graphic"
            if raw:
                block_data.raw = raw
            if source_line > 0:
                block_data.source_line = source_line
            return block_data

        source_segments = getattr(block_data, "source_segments", None)
        if not isinstance(source_segments, (list, tuple)):
            source_segments = []

        try:
            depth = int(getattr(block_data, "depth", 0) or 0)
        except (TypeError, ValueError):
            depth = 0

        return _BlockMeta(
            kind="graphic",
            command=str(getattr(block_data, "command", "") or ""),
            raw=raw,
            display=str(getattr(block_data, "display", "") or ""),
            depth=depth,
            source_line=max(int(source_line), 0),
            source_segments=list(source_segments),
        )
