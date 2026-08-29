"""Keep Preview controls persistent and own window-scoped Preview/image interactions."""

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QToolButton

from nd_mind_mirror.ui.window.main.graphic_source_context_controller import (
    GraphicSourceContextController,
)
from nd_mind_mirror.ui.window.main.preview_detach_controller import PreviewDetachController


class PreviewToggleButtonController(QObject):
    """Mirror Preview QAction and keep its related window-level controllers alive."""

    def __init__(self, window: QMainWindow, action: QAction, parent=None) -> None:
        super().__init__(parent or window)
        self._window = window
        self._action = action
        self._button = QToolButton(window)
        self._button.setText("Preview")
        self._button.setCheckable(True)
        self._button.setChecked(action.isChecked())
        self._button.setToolTip("Toggle LaTeX preview")
        self._button.setAutoRaise(False)
        self._button.toggled.connect(self._action.setChecked)
        self._action.toggled.connect(self._sync_from_action)
        self._window.menuBar().setCornerWidget(
            self._button,
            Qt.Corner.TopRightCorner,
        )
        self._apply_checked_style(self._button.isChecked())

        self._preview_detach_controller = PreviewDetachController(
            window,
            action,
            self,
        )
        self._graphic_source_context_controller = GraphicSourceContextController(
            window,
            self,
        )

    def _sync_from_action(self, checked: bool) -> None:
        """Update the button without recursively re-triggering the QAction."""
        if self._button.isChecked() != checked:
            self._button.blockSignals(True)
            self._button.setChecked(checked)
            self._button.blockSignals(False)
        self._apply_checked_style(checked)

    def _apply_checked_style(self, checked: bool) -> None:
        """Use a subtle light-gray fill only while Preview is open."""
        if checked:
            self._button.setStyleSheet(
                "QToolButton {"
                " background-color: rgba(160, 160, 160, 45);"
                " border: 1px solid rgba(120, 120, 120, 65);"
                " border-radius: 3px;"
                " padding: 2px 8px;"
                " }"
            )
        else:
            self._button.setStyleSheet("")
