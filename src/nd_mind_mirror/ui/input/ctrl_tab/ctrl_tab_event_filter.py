from PySide6.QtCore import QObject, QEvent, Qt, Signal


class CtrlTabEventFilter(QObject):
    cycle_requested = Signal(int)
    commit_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def eventFilter(self, watched, event) -> bool:
        event_type = event.type()

        if event_type == QEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()

            if (
                key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
                and bool(
                    modifiers
                    & Qt.KeyboardModifier.ControlModifier
                )
                and not bool(
                    modifiers
                    & (
                        Qt.KeyboardModifier.AltModifier
                        | Qt.KeyboardModifier.MetaModifier
                    )
                )
            ):
                backward = (
                    key == Qt.Key.Key_Backtab
                    or bool(
                        modifiers
                        & Qt.KeyboardModifier.ShiftModifier
                    )
                )
                self._active = True
                self.cycle_requested.emit(
                    -1 if backward else 1
                )
                event.accept()
                return True

            if (
                self._active
                and key == Qt.Key.Key_Escape
            ):
                self._active = False
                self.cancel_requested.emit()
                event.accept()
                return True

        if event_type == QEvent.Type.KeyRelease:
            if (
                self._active
                and event.key()
                in (
                    Qt.Key.Key_Control,
                )
            ):
                self._active = False
                self.commit_requested.emit()
                event.accept()
                return True

        return super().eventFilter(
            watched,
            event,
        )
