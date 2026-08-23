"""Keep LaTeX Preview Auto Fit fixed after one stable full-page width calculation."""

from PySide6.QtCore import QEvent, QMetaObject, QObject, QTimer, Qt
from PySide6.QtWidgets import QMenu


class PreviewAutoFitController(QObject):
    """Fit the physical PDF page once, then preserve that zoom until Auto Fit is toggled."""

    _WIDTH_EPSILON_PX = 2
    _REFIT_DELAY_MS = 180
    _RECENTER_DELAY_MS = 220
    _LATE_RECENTER_DELAY_MS = 620
    _DEFAULT_FIT_WIDTH_RATIO = 0.95

    def __init__(self, preview_panel, main_splitter, session_settings, parent=None) -> None:
        super().__init__(parent)
        self._panel = preview_panel
        self._preview = preview_panel.preview
        self._pdf_view = self._preview._pdf_view
        self._splitter = main_splitter
        self._settings = session_settings

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._REFIT_DELAY_MS)
        self._timer.timeout.connect(self._refit_if_width_is_stable)

        self._recenter_timer = QTimer(self)
        self._recenter_timer.setSingleShot(True)
        self._recenter_timer.setInterval(self._RECENTER_DELAY_MS)
        self._recenter_timer.timeout.connect(self._recenter_after_reload)

        self._late_recenter_timer = QTimer(self)
        self._late_recenter_timer.setSingleShot(True)
        self._late_recenter_timer.setInterval(self._LATE_RECENTER_DELAY_MS)
        self._late_recenter_timer.timeout.connect(self._recenter_after_reload)

        self._auto_enabled = bool(
            self._settings.value("preview/continuous_auto_fit", False, type=bool)
        )
        self._auto_fit_applied = False
        self._last_applied_width: int | None = None
        self._pending_width: int | None = None

        self._install_menu()
        self._panel.installEventFilter(self)
        self._splitter.splitterMoved.connect(self._schedule_refit)
        self._pdf_view.user_zoomed.connect(self._disable_after_manual_zoom)
        self._panel._zoom_edit.editingFinished.connect(self._disable_after_manual_zoom)
        self._connect_reload_signal()

        if self._auto_enabled:
            QTimer.singleShot(self._REFIT_DELAY_MS, self._schedule_refit)

    def eventFilter(self, watched, event) -> bool:
        if watched is self._panel and event.type() == QEvent.Type.Resize:
            self._schedule_refit()
        return super().eventFilter(watched, event)

    def set_auto_fit(self, enabled: bool) -> None:
        self._auto_enabled = bool(enabled)
        self._auto_action.blockSignals(True)
        self._auto_action.setChecked(self._auto_enabled)
        self._auto_action.blockSignals(False)
        self._settings.setValue("preview/continuous_auto_fit", self._auto_enabled)
        self._settings.sync()

        self._timer.stop()
        self._recenter_timer.stop()
        self._late_recenter_timer.stop()
        self._auto_fit_applied = False
        self._last_applied_width = None
        self._pending_width = None

        if self._auto_enabled:
            # Auto Fit intentionally chooses its width only once. Wait until
            # the outer preview width is stable before making that one choice.
            self._timer.start()

    def _install_menu(self) -> None:
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
            "Fit Once is content-aware. Auto Fit fits the complete PDF page "
            "once to the current Preview width, then keeps that zoom unchanged "
            "during typing, PDF reloads, window/layout changes, and splitter moves. "
            "Toggle Auto Fit off and on to choose a new width."
        )

    def _connect_reload_signal(self) -> None:
        """Recenter after each QML PDF reload without changing the locked zoom."""
        try:
            root = self._pdf_view.rootObject()
            if root is None:
                return
            reload_signal = getattr(root, "reloadTokenChanged", None)
            if reload_signal is not None:
                reload_signal.connect(self._on_preview_reloaded)
        except (AttributeError, RuntimeError, TypeError):
            return

    def _viewport_width(self) -> int:
        """Return the stable outer PDF viewport width."""
        try:
            width = int(self._pdf_view.width())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            width = int(self._panel.width())
        return max(width, 0)

    def _schedule_refit(self, *args) -> None:
        del args
        if not self._auto_enabled or self._auto_fit_applied:
            return
        self._timer.start()

    def _refit_if_width_is_stable(self) -> None:
        if not self._auto_enabled or self._auto_fit_applied:
            return

        width = self._viewport_width()
        if width <= 1:
            self._timer.start()
            return

        try:
            page_count = int(self._pdf_view._fit_document.pageCount())
        except Exception:
            page_count = 0
        if page_count <= 0:
            self._timer.start()
            return

        if (
            self._pending_width is None
            or abs(width - self._pending_width) > self._WIDTH_EPSILON_PX
        ):
            self._pending_width = width
            self._timer.start()
            return

        self._last_applied_width = width
        self._pending_width = None
        self._apply_fit()
        self._auto_fit_applied = True

    def _apply_fit(self) -> None:
        """Fit the complete physical current PDF page to the stable outer Preview width."""
        if not self._auto_enabled:
            return

        root = self._pdf_view.rootObject()
        if root is None:
            return

        document = self._pdf_view._fit_document
        try:
            page_count = int(document.pageCount())
        except Exception:
            page_count = 0
        if page_count <= 0:
            return

        try:
            page_index = max(int(root.property("currentPageIndex")), 0)
        except (TypeError, ValueError):
            page_index = 0
        page_index = min(page_index, page_count - 1)

        try:
            page_size = document.pagePointSize(page_index)
            page_width_points = float(page_size.width())
        except Exception:
            page_width_points = 0.0
        if page_width_points <= 1.0:
            return

        viewport_width = self._viewport_width()
        if viewport_width <= 1:
            return

        try:
            ratio = float(root.property("fitWidthRatio"))
        except (TypeError, ValueError):
            ratio = self._DEFAULT_FIT_WIDTH_RATIO
        if not (0.0 < ratio <= 1.0):
            ratio = self._DEFAULT_FIT_WIDTH_RATIO

        scale = (float(viewport_width) * ratio) / page_width_points
        scale = max(self._pdf_view._MIN_ZOOM, min(scale, self._pdf_view._MAX_ZOOM))

        root.setProperty("fitPageWidthPoints", page_width_points)
        root.setProperty("fitContentWidthPoints", 0.0)
        root.setProperty("fitContentCenterRatioX", 0.5)
        root.setProperty("zoomScale", float(scale))
        self._schedule_recenter()

    def _on_preview_reloaded(self) -> None:
        """Keep the chosen Auto Fit zoom; reloads may only repair centering."""
        if not self._auto_enabled:
            return
        self._schedule_recenter()

    def _schedule_recenter(self) -> None:
        if not self._auto_enabled:
            return
        self._recenter_timer.start()
        self._late_recenter_timer.start()

    def _recenter_after_reload(self) -> None:
        if not self._auto_enabled:
            return
        try:
            root = self._pdf_view.rootObject()
            if root is None:
                return
            QMetaObject.invokeMethod(
                root,
                "centerHorizontally",
                Qt.ConnectionType.DirectConnection,
            )
        except (AttributeError, RuntimeError, TypeError):
            return

    def _disable_after_manual_zoom(self) -> None:
        if self._auto_enabled:
            self.set_auto_fit(False)
