"""Add continuous Auto Fit behavior to the existing LaTeX preview Fit control."""

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QMenu


class PreviewAutoFitController(QObject):
    """Re-fit the PDF after preview/sidebar resizing while Auto Fit is enabled."""

    def __init__(self, preview_panel, main_splitter, session_settings, parent=None) -> None:
        """Turn the Fit button into a Fit/Auto Fit menu and restore its persisted mode."""
        super().__init__(parent)
        self._panel = preview_panel
        self._preview = preview_panel.preview
        self._splitter = main_splitter
        self._settings = session_settings
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._refit_if_enabled)
        self._auto_enabled = bool(
            self._settings.value("preview/continuous_auto_fit", False, type=bool)
        )
        self._install_menu()
        self._panel.installEventFilter(self)
        self._splitter.splitterMoved.connect(self._schedule_refit)
        self._preview._pdf_view.user_zoomed.connect(self._disable_after_manual_zoom)
        self._panel._zoom_edit.editingFinished.connect(self._disable_after_manual_zoom)

    def eventFilter(self, watched, event) -> bool:
        """Schedule a fit when the preview panel itself is resized in Auto Fit mode."""
        if watched is self._panel and event.type() == QEvent.Type.Resize:
            self._schedule_refit()
        return super().eventFilter(watched, event)

    def set_auto_fit(self, enabled: bool) -> None:
        """Persist Auto Fit state and immediately fit when the mode is enabled."""
        self._auto_enabled = bool(enabled)
        self._auto_action.blockSignals(True)
        self._auto_action.setChecked(self._auto_enabled)
        self._auto_action.blockSignals(False)
        self._settings.setValue("preview/continuous_auto_fit", self._auto_enabled)
        self._settings.sync()
        if self._auto_enabled:
            self._preview.fit_to_panel()

    def _install_menu(self) -> None:
        """Replace the single Fit click with explicit Fit Once and Auto Fit choices."""
        button = self._panel._fit_button
        try:
            button.clicked.disconnect(self._preview.fit_to_panel)
        except (RuntimeError, TypeError):
            pass
        menu = QMenu(button)
        fit_action = menu.addAction("Fit Once")
        fit_action.triggered.connect(self._preview.fit_to_panel)
        self._auto_action = menu.addAction("Auto Fit")
        self._auto_action.setCheckable(True)
        self._auto_action.setChecked(self._auto_enabled)
        self._auto_action.toggled.connect(self.set_auto_fit)
        button.setText("Fit")
        button.setMenu(menu)
        button.setToolTip(
            "Fit Once recalculates the current PDF scale. Auto Fit recalculates whenever the preview width changes."
        )

    def _schedule_refit(self, *args) -> None:
        """Debounce repeated splitter/resize events before recalculating Fit."""
        del args
        if self._auto_enabled:
            self._timer.start()

    def _refit_if_enabled(self) -> None:
        """Recalculate content-aware Fit only when Auto Fit is still active."""
        if self._auto_enabled:
            self._preview.fit_to_panel()

    def _disable_after_manual_zoom(self) -> None:
        """Leave continuous Auto Fit when the user explicitly zooms the PDF."""
        if self._auto_enabled:
            self.set_auto_fit(False)
