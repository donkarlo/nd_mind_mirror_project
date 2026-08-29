"""Route source/visual image context clicks to the exact graphic under the pointer."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor


class GraphicSourceContextController(QObject):
    """Prevent stale editor selections from opening an unrelated img_0 sidecar."""

    def __init__(self, window, parent=None) -> None:
        super().__init__(parent or window)
        self._window = window
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if event.type() != QEvent.Type.ContextMenu:
            return super().eventFilter(watched, event)

        source_editor = self._source_editor_for(watched)
        visual_editor = self._visual_editor_for(watched)
        if source_editor is None and visual_editor is None:
            return super().eventFilter(watched, event)

        if visual_editor is not None:
            source_editor = self._owning_source_editor(visual_editor)
            if source_editor is None:
                return super().eventFilter(watched, event)
            click_point = self._viewport_point(visual_editor, watched, event.pos())
            click_cursor = visual_editor.cursorForPosition(click_point)
            line, column = visual_editor.source_location_for_position(click_cursor.position())
            position = source_editor._source_position_for_location((line, column))
            menu_owner = visual_editor
        else:
            assert source_editor is not None
            click_point = self._viewport_point(source_editor, watched, event.pos())
            click_cursor = source_editor.cursorForPosition(click_point)
            position = click_cursor.position()
            line = column = 1
            menu_owner = source_editor

        existing = source_editor._graphic_manager.find_reference(
            source_editor.toPlainText(),
            source_editor._source_path,
            position,
        )
        menu = menu_owner.createStandardContextMenu()
        menu.addSeparator()
        graphic_action = menu.addAction(
            "Edit image in iPad…" if existing is not None else "Insert image in iPad…"
        )
        chosen = menu.exec(event.globalPos())
        if chosen != graphic_action:
            return True

        if existing is not None:
            source_editor._request_ipad_open(existing.sidecar_path, operation="update")
            return True

        if visual_editor is not None:
            source_editor._handle_graphic_request(line, column)
        else:
            source_editor.setTextCursor(click_cursor)
            line, column = source_editor.active_source_location()
            source_editor._handle_graphic_request(line, column)
        return True

    @staticmethod
    def _viewport_point(editor, watched, point):
        if watched is editor.viewport():
            return point
        try:
            return editor.viewport().mapFrom(watched, point)
        except (AttributeError, RuntimeError, TypeError):
            return point

    @staticmethod
    def _source_editor_for(widget) -> LatexEditor | None:
        if isinstance(widget, LatexEditor):
            return widget
        parent = getattr(widget, "parent", lambda: None)()
        return parent if isinstance(parent, LatexEditor) else None

    @staticmethod
    def _visual_editor_for(widget) -> LatexVisualEditor | None:
        if isinstance(widget, LatexVisualEditor):
            return widget
        parent = getattr(widget, "parent", lambda: None)()
        return parent if isinstance(parent, LatexVisualEditor) else None

    @staticmethod
    def _owning_source_editor(visual_editor: LatexVisualEditor) -> LatexEditor | None:
        parent = visual_editor.parent()
        while parent is not None:
            if isinstance(parent, LatexEditor):
                return parent
            parent = parent.parent()
        return None
