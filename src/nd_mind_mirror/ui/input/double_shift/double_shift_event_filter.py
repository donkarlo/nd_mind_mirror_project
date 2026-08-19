import time

from PySide6.QtCore import (
    QEvent,
    QObject,
    Qt,
    Signal,
)


class DoubleShiftEventFilter(QObject):
    activated = Signal()

    def __init__(
        self,
        interval_ms: int = 450,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._interval_seconds = max(
            int(interval_ms),
            100,
        ) / 1000.0
        self._last_shift_tap_time = 0.0
        self._shift_pressed = False
        self._shift_used_as_modifier = False

    def set_interval_ms(
        self,
        interval_ms: int,
    ) -> None:
        self._interval_seconds = max(
            int(interval_ms),
            100,
        ) / 1000.0
        self._reset_sequence()

    def eventFilter(
        self,
        watched,
        event,
    ) -> bool:
        event_type = event.type()

        if event_type not in {
            QEvent.Type.KeyPress,
            QEvent.Type.KeyRelease,
        }:
            return False

        if event.isAutoRepeat():
            return False

        key = event.key()

        if event_type == QEvent.Type.KeyPress:
            return self._handle_key_press(
                key,
                event.modifiers(),
            )

        return self._handle_key_release(key)

    def _handle_key_press(
        self,
        key: int,
        modifiers: Qt.KeyboardModifier,
    ) -> bool:
        if key != Qt.Key.Key_Shift:
            if self._shift_pressed:
                self._shift_used_as_modifier = True
            self._last_shift_tap_time = 0.0
            return False

        forbidden_modifiers = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )

        if bool(modifiers & forbidden_modifiers):
            self._shift_pressed = False
            self._shift_used_as_modifier = False
            self._last_shift_tap_time = 0.0
            return False

        self._shift_pressed = True
        self._shift_used_as_modifier = False
        return False

    def _handle_key_release(
        self,
        key: int,
    ) -> bool:
        if key != Qt.Key.Key_Shift:
            return False

        if not self._shift_pressed:
            return False

        was_modifier = self._shift_used_as_modifier
        self._shift_pressed = False
        self._shift_used_as_modifier = False

        if was_modifier:
            self._last_shift_tap_time = 0.0
            return False

        now = time.monotonic()

        if (
            self._last_shift_tap_time > 0
            and now - self._last_shift_tap_time
            <= self._interval_seconds
        ):
            self._last_shift_tap_time = 0.0
            self.activated.emit()
            return False

        self._last_shift_tap_time = now
        return False

    def _reset_sequence(self) -> None:
        self._last_shift_tap_time = 0.0
        self._shift_pressed = False
        self._shift_used_as_modifier = False
