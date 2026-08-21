"""Keep a persistent Preview toggle button in the main window's top-right menu-bar corner."""

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QToolButton


class PreviewToggleButtonController(QObject):
    """Mirror the existing checkable Preview QAction into an always-visible top-right button."""

    def __init__(self, window: QMainWindow, action: QAction, parent=None) -> None:
        """Create the persistent button and keep its checked state synchronized with the Preview action."""
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

    def _sync_from_action(self, checked: bool) -> None:
        """Update the button without recursively re-triggering the QAction."""
        if self._button.isChecked() == checked:
            return
        self._button.blockSignals(True)
        self._button.setChecked(checked)
        self._button.blockSignals(False)
