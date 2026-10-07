"""Detach, hide, and reattach the live Preview without stretching the editor."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QMainWindow, QPushButton


class PreviewDetachController(QObject):
    """Own Preview placement while preserving the main window's left-side width."""

    def __init__(self, window, action, parent=None) -> None:
        super().__init__(parent or window)
        self._window = window
        self._action = action
        self._panel = window._preview_panel
        self._splitter = window._splitter
        self._detached = False
        self._main_collapsed = False
        self._preview_width = max(self._panel.width(), 360)
        self._left_sizes: list[int] = []
        self._shrink_delta = 0
        self._was_maximized = False

        self._detached_window = QMainWindow(window, Qt.WindowType.Window)
        self._detached_window.setWindowTitle("Preview")
        self._detached_window.installEventFilter(self)

        self._detach_button = QPushButton("Detach", self._panel)
        self._detach_button.setToolTip("Move Preview to its own window")
        self._detach_button.clicked.connect(self.toggle_detached)
        controls = getattr(self._panel, "_controls_layout", None)
        if controls is not None:
            controls.insertWidget(2, self._detach_button)

        try:
            self._action.toggled.disconnect(self._window._set_preview_enabled)
        except (RuntimeError, TypeError):
            pass
        self._action.toggled.connect(self._set_preview_enabled)

        if not self._action.isChecked():
            QTimer.singleShot(0, self._apply_initial_hidden_state)

    def eventFilter(self, watched, event) -> bool:
        if watched is self._detached_window and event.type() == QEvent.Type.Close:
            event.ignore()
            self._action.setChecked(False)
            return True
        return super().eventFilter(watched, event)

    def toggle_detached(self) -> None:
        if self._detached:
            self._attach()
        else:
            self._detach()

    def _set_preview_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._detached:
            self._window._set_preview_enabled(enabled)
            if enabled:
                self._detached_window.show()
                self._detached_window.raise_()
            else:
                self._detached_window.hide()
            return

        if enabled:
            self._expand_main_window()
            self._window._set_preview_enabled(True)
            self._restore_splitter_sizes()
        else:
            self._capture_attached_layout()
            self._window._set_preview_enabled(False)
            self._shrink_main_window()

    def _apply_initial_hidden_state(self) -> None:
        if self._action.isChecked() or self._detached:
            return
        self._capture_attached_layout()
        self._shrink_main_window()

    def _capture_attached_layout(self) -> None:
        sizes = list(self._splitter.sizes())
        if len(sizes) >= 3:
            self._left_sizes = [max(int(sizes[0]), 1), max(int(sizes[1]), 1)]
            if sizes[2] > 40:
                self._preview_width = int(sizes[2])
        else:
            self._preview_width = max(self._panel.width(), self._preview_width, 360)
        self._preview_width = max(self._preview_width, 240)
        self._shrink_delta = self._preview_width + max(self._splitter.handleWidth(), 1)

    def _shrink_main_window(self) -> None:
        if self._main_collapsed:
            return
        self._was_maximized = bool(self._window.isMaximized())
        geometry = self._window.normalGeometry() if self._was_maximized else self._window.geometry()
        if self._was_maximized:
            self._window.showNormal()
        width = max(self._window.minimumWidth(), geometry.width() - max(self._shrink_delta, 1))
        self._window.setGeometry(geometry.x(), geometry.y(), width, geometry.height())
        self._main_collapsed = True
        if self._left_sizes:
            self._splitter.setSizes([*self._left_sizes, 0])

    def _expand_main_window(self) -> None:
        if not self._main_collapsed:
            return
        geometry = self._window.geometry()
        self._window.setGeometry(
            geometry.x(),
            geometry.y(),
            geometry.width() + max(self._shrink_delta, 1),
            geometry.height(),
        )
        self._main_collapsed = False
        if self._was_maximized:
            self._window.showMaximized()
        self._was_maximized = False

    def _restore_splitter_sizes(self) -> None:
        if self._left_sizes:
            self._splitter.setSizes([*self._left_sizes, max(self._preview_width, 240)])

    def _detach(self) -> None:
        if self._detached or not self._action.isChecked():
            return
        self._capture_attached_layout()
        self._panel.setParent(None)
        self._detached_window.setCentralWidget(self._panel)
        self._detached_window.resize(max(self._preview_width, 420), max(self._window.height(), 480))
        self._panel.show()
        self._detached_window.show()
        self._detached_window.raise_()
        self._detached = True
        self._detach_button.setText("Attach")
        self._detach_button.setToolTip("Return Preview to the main window")
        self._shrink_main_window()

    def _attach(self) -> None:
        if not self._detached:
            return
        self._detached_window.takeCentralWidget()
        self._panel.setParent(self._splitter)
        self._splitter.insertWidget(2, self._panel)
        self._detached = False
        self._detach_button.setText("Detach")
        self._detach_button.setToolTip("Move Preview to its own window")
        self._detached_window.hide()
        self._expand_main_window()
        self._window._set_preview_enabled(self._action.isChecked())
        self._restore_splitter_sizes()
