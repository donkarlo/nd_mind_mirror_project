"""Preserve legacy controller wiring while delegating context menus to editors.

Source and Visual now own their complete context menus. Keeping a second
application-level context-menu implementation here would consume the event
before the editor can expose bookmark, image, TikZ, and raw-LaTeX actions.
"""

from __future__ import annotations

from PySide6.QtCore import QObject


class GraphicSourceContextController(QObject):
    """Do not intercept Source/Visual context menus.

    The controller remains constructible for older window-composition code,
    but context-menu ownership belongs to the active LaTeX editor and its
    Visual context controller. Those owners already resolve the exact click
    position for image and TikZ actions.
    """

    def __init__(self, window, parent=None) -> None:
        super().__init__(parent or window)
        self._window = window
