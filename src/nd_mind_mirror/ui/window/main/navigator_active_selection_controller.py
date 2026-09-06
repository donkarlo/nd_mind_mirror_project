"""Keep the Navigator selection synchronized with the active editor tab."""

from __future__ import annotations

from PySide6.QtCore import QObject, Slot


class NavigatorActiveSelectionController(QObject):
    """Reveal and highlight the backing file whenever the active editor changes."""

    def __init__(self, editor_panel, file_system_panel, parent=None) -> None:
        super().__init__(parent)
        self._file_system_panel = file_system_panel
        editor_panel.current_document_changed.connect(self._on_current_document_changed)

    @Slot(str, str)
    def _on_current_document_changed(self, path: str, _content: str) -> None:
        """Force the active document row to become the visible Navigator selection."""
        if not path:
            return
        self._file_system_panel.select_path(path, force_reveal=True)
