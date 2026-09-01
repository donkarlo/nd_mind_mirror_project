"""Control when Double-Shift file search begins while the user is typing."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject


class SearchTypingController(QObject):
    """Require a short typing pause before starting an indexed file search."""

    _MINIMUM_PAUSE_MS = 280

    def __init__(self, search_window, parent=None) -> None:
        super().__init__(parent)
        self._search_window = search_window
        self._search_window.installEventFilter(self)
        self.apply()

    def eventFilter(self, watched, event) -> bool:
        if watched is self._search_window and event.type() in {
            QEvent.Type.Show,
            QEvent.Type.ShowToParent,
        }:
            self.apply()
        return super().eventFilter(watched, event)

    def apply(self) -> None:
        """Keep slower user-configured values while migrating the old 70 ms cadence."""
        timer = getattr(self._search_window, "_debounce_timer", None)
        if timer is None:
            return
        timer.setInterval(max(int(timer.interval()), self._MINIMUM_PAUSE_MS))
