"""Detect Double Shift and protect Search activation from focus races."""

import time

from PySide6.QtCore import (
    QEvent,
    QObject,
    Qt,
    Signal,
)

from nd_mind_mirror.ui.input.double_shift.activation_key_handoff_buffer import (
    ActivationKeyHandoffBuffer,
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
        self._activation_handoff = ActivationKeyHandoffBuffer(
            timeout_ms=1200,
            parent=self,
        )

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
        # Once Double Shift has fired, the handoff owns keyboard input until
        # Search's QLineEdit really receives focus. This prevents early text
        # from entering Source or disappearing during window activation.
        if self._activation_handoff.intercept(watched, event):
            return True

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

            # Arm before emitting: the signal synchronously opens Search, while
            # a top-level window manager may complete focus transfer later.
            self._activation_handoff.begin()
            self.activated.emit()

            # The second Shift release belongs to the shortcut itself.
            return True

        self._last_shift_tap_time = now
        return False

    def _reset_sequence(self) -> None:
        self._last_shift_tap_time = 0.0
        self._shift_pressed = False
        self._shift_used_as_modifier = False
