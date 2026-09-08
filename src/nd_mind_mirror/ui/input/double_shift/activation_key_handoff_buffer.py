"""Buffer keystrokes while Double-Shift Search takes keyboard focus."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit


class ActivationKeyHandoffBuffer(QObject):
    """Protect text typed between shortcut activation and Search focus."""

    _DEFAULT_TIMEOUT_MS = 1200

    def __init__(
        self,
        timeout_ms: int = _DEFAULT_TIMEOUT_MS,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._active = False
        self._pending_key_presses: list[
            tuple[int, Qt.KeyboardModifier, str, bool, int]
        ] = []
        self._captured_keys: set[int] = set()

        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.setInterval(max(int(timeout_ms), 250))
        self._timeout_timer.timeout.connect(self.cancel)

    @property
    def is_active(self) -> bool:
        return self._active

    def begin(self) -> None:
        """Start a fresh focus handoff immediately before Search is requested."""
        self._active = True
        self._pending_key_presses.clear()
        self._captured_keys.clear()
        self._timeout_timer.start()

    def cancel(self) -> None:
        """Release the keyboard guard if Search never receives focus."""
        self._active = False
        self._pending_key_presses.clear()
        self._captured_keys.clear()
        self._timeout_timer.stop()

    def intercept(self, watched, event) -> bool:
        """Capture input until the activated Search line edit receives focus."""
        if not self._active:
            return False

        event_type = event.type()

        if (
            event_type == QEvent.Type.FocusIn
            and isinstance(watched, QLineEdit)
        ):
            self._finish_handoff(watched)
            return False

        if event_type == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            return self._capture_key_press(event)

        if event_type == QEvent.Type.KeyRelease and isinstance(event, QKeyEvent):
            key = int(event.key())
            if key in self._captured_keys:
                self._captured_keys.discard(key)
                return True

        return False

    def _capture_key_press(self, event: QKeyEvent) -> bool:
        """Store one user key press and prevent it reaching the old editor."""
        key = int(event.key())

        # Modifier-only presses are irrelevant to a search query. They remain
        # consumed during the brief handoff so they cannot alter the old editor.
        text = str(event.text())
        if text or key in {
            int(Qt.Key.Key_Backspace),
            int(Qt.Key.Key_Delete),
            int(Qt.Key.Key_Return),
            int(Qt.Key.Key_Enter),
        }:
            self._pending_key_presses.append(
                (
                    key,
                    event.modifiers(),
                    text,
                    bool(event.isAutoRepeat()),
                    max(int(event.count()), 1),
                )
            )

        self._captured_keys.add(key)
        return True

    def _finish_handoff(self, target: QLineEdit) -> None:
        """Replay captured keys in order, then return normal input routing."""
        pending = tuple(self._pending_key_presses)

        self._active = False
        self._pending_key_presses.clear()
        self._captured_keys.clear()
        self._timeout_timer.stop()

        for key, modifiers, text, auto_repeat, count in pending:
            replay = QKeyEvent(
                QEvent.Type.KeyPress,
                key,
                modifiers,
                text,
                auto_repeat,
                count,
            )
            QApplication.sendEvent(target, replay)
