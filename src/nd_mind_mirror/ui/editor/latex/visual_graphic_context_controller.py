"""Normalize existing Visual graphic blocks before their context menu is built."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor


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
            block_data = cursor.block().userData()
            raw = str(getattr(block_data, "raw", "") or "")
            if block_data is not None and (
                "\\includegraphics" in raw or cursor.charFormat().isImageFormat()
            ):
                try:
                    block_data.kind = "graphic"
                except (AttributeError, RuntimeError):
                    pass
        return super().eventFilter(watched, event)
