"""Track active Source typing bursts so disruptive window reloads wait for idle."""

from PySide6.QtCore import QObject, QTimer, Signal


class SourceTypingBurstController(QObject):
    """Expose whether Source typing is active and emit once the burst becomes idle."""

    became_idle = Signal()

    def __init__(self, idle_ms: int = 180, parent=None) -> None:
        super().__init__(parent)
        self._active = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(max(int(idle_ms), 80))
        self._timer.timeout.connect(self._finish_burst)

    @property
    def is_active(self) -> bool:
        return bool(self._active)

    def note_activity(self) -> None:
        """Restart the idle deadline after each real character edit."""
        self._active = True
        self._timer.start()

    def _finish_burst(self) -> None:
        self._active = False
        self.became_idle.emit()
