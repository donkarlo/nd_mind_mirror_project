"""Keep Preview fitting stable while removing redundant runtime work."""

from __future__ import annotations

from pathlib import Path
from time import monotonic
from types import MethodType

from PySide6.QtCore import QEvent, QMetaObject, QObject, QTimer, Qt
from PySide6.QtWidgets import QMenu


class PreviewAutoFitController(QObject):
    """Fit a physical PDF page once and keep Preview interaction inexpensive."""

    _FIT_DELAY_MS = 140
    _DEFAULT_FIT_WIDTH_RATIO = 0.95
    _MAX_READY_RETRIES = 8
    _MANUAL_SCROLL_SUPPRESSION_SECONDS = 1.25

    def __init__(
        self,
        preview_panel,
        main_splitter,
        session_settings,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._panel = preview_panel
        self._preview = preview_panel.preview
        self._pdf_view = self._preview._pdf_view
        self._splitter = main_splitter
        self._settings = session_settings

        self._auto_enabled = bool(
            self._settings.value(
                "preview/continuous_auto_fit",
                False,
                type=bool,
            )
        )
        self._applied_document_key: str | None = None
        self._ready_retry_count = 0
        self._manual_scroll_until = 0.0

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._FIT_DELAY_MS)
        self._timer.timeout.connect(self._apply_auto_fit_if_ready)

        # QML owns PDF reload/scroll preservation. Do not run a second Python
        # restore loop for the same state.
        try:
            self._preview.configure_initial_view(
                False,
                int(getattr(self._preview, "_fit_width_percent", 95)),
            )
            self._preview._fit_active = False
            self._preview._fit_pending_for_source = False
            self._preview._view_restore_generation += 1
        except Exception:
            pass

        self._install_fit_menu()
        self._install_sync_guard()

        self._panel.installEventFilter(self)
        self._pdf_view.installEventFilter(self)
        self._splitter.splitterMoved.connect(self._schedule_auto_fit)
        self._pdf_view.user_zoomed.connect(self._disable_after_manual_zoom)
        self._panel._zoom_edit.editingFinished.connect(
            self._disable_after_manual_zoom
        )
        try:
            self._preview.view_status_changed.connect(
                self._on_view_status_changed
            )
        except Exception:
            pass

        # Runs only after all EnhancedMainWindow/runtime controllers have been
        # constructed, so redundant overlays/timers can be removed safely.
        QTimer.singleShot(0, self._remove_redundant_runtime_layers)

        if self._auto_enabled:
            QTimer.singleShot(self._FIT_DELAY_MS, self._schedule_auto_fit)

    def eventFilter(self, watched, event) -> bool:
        event_type = event.type()

        if watched is self._panel and event_type == QEvent.Type.Resize:
            if self._auto_enabled and self._applied_document_key is None:
                self._schedule_auto_fit()

        manual_preview_interaction = False
        if watched is self._pdf_view:
            if event_type in {
                QEvent.Type.Wheel,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.TouchBegin,
                QEvent.Type.TouchUpdate,
            }:
                manual_preview_interaction = True
            elif event_type == QEvent.Type.MouseMove:
                try:
                    manual_preview_interaction = bool(event.buttons())
                except (AttributeError, RuntimeError, TypeError):
                    manual_preview_interaction = False

        if manual_preview_interaction:
            self._manual_scroll_until = (
                monotonic() + self._MANUAL_SCROLL_SUPPRESSION_SECONDS
            )

        return super().eventFilter(watched, event)

    def set_auto_fit(self, enabled: bool) -> None:
        self._auto_enabled = bool(enabled)
        self._auto_action.blockSignals(True)
        self._auto_action.setChecked(self._auto_enabled)
        self._auto_action.blockSignals(False)
        self._settings.setValue(
            "preview/continuous_auto_fit",
            self._auto_enabled,
        )
        self._settings.sync()

        self._timer.stop()
        self._applied_document_key = None
        self._ready_retry_count = 0
        if self._auto_enabled:
            self._timer.start()

    def _install_fit_menu(self) -> None:
        button = self._panel._fit_button
        try:
            button.clicked.disconnect(self._preview.fit_to_panel)
        except (RuntimeError, TypeError):
            pass

        menu = QMenu(button)
        fit_action = menu.addAction("Fit Once")
        fit_action.triggered.connect(self._fit_once)

        self._auto_action = menu.addAction("Auto Fit")
        self._auto_action.setCheckable(True)
        self._auto_action.setChecked(self._auto_enabled)
        self._auto_action.toggled.connect(self.set_auto_fit)

        button.setText("Fit")
        button.setMenu(menu)
        button.setToolTip(
            "Fit Once fits the complete physical PDF page width. "
            "Auto Fit performs the same inexpensive fit once for a newly "
            "opened LaTeX document and keeps zoom fixed during live reloads."
        )

    def _install_sync_guard(self) -> None:
        original = self._pdf_view.scroll_to_pdf_location

        def guarded_scroll_to_pdf_location(
            view,
            page: int,
            x: float,
            y: float,
            *,
            keep_horizontal_center: bool = False,
        ) -> None:
            del view
            if monotonic() < self._manual_scroll_until:
                return
            original(
                page,
                x,
                y,
                keep_horizontal_center=keep_horizontal_center,
            )

        self._pdf_view.scroll_to_pdf_location = MethodType(
            guarded_scroll_to_pdf_location,
            self._pdf_view,
        )

    def _on_view_status_changed(
        self,
        _zoom_percent: float,
        _page_number: int,
        page_count: int,
    ) -> None:
        if page_count > 0:
            self._schedule_auto_fit()

    def _schedule_auto_fit(self, *args) -> None:
        del args
        if not self._auto_enabled:
            return

        document_key = self._document_key()
        if document_key is not None and document_key != self._applied_document_key:
            self._ready_retry_count = 0

        if document_key is not None and document_key == self._applied_document_key:
            return
        self._timer.start()

    def _apply_auto_fit_if_ready(self) -> None:
        if not self._auto_enabled:
            return

        document_key = self._document_key()
        if document_key is None:
            self._retry_if_reasonable()
            return

        if document_key == self._applied_document_key:
            return

        if not self._fit_physical_page_width():
            self._retry_if_reasonable()
            return

        self._applied_document_key = document_key
        self._ready_retry_count = 0

    def _retry_if_reasonable(self) -> None:
        self._ready_retry_count += 1
        if self._ready_retry_count <= self._MAX_READY_RETRIES:
            self._timer.start()

    def _fit_once(self) -> None:
        self._timer.stop()
        self._ready_retry_count = 0
        if self._fit_physical_page_width():
            self._applied_document_key = self._document_key()

    def _fit_physical_page_width(self) -> bool:
        """Fit one real PDF page width without text extraction or raster scans."""
        root = self._pdf_view.rootObject()
        if root is None:
            return False

        viewport_width = self._viewport_width()
        if viewport_width <= 1:
            return False

        document = self._pdf_view._fit_document
        try:
            page_count = int(document.pageCount())
        except Exception:
            page_count = 0
        if page_count <= 0:
            return False

        try:
            page_index = int(root.property("currentPageIndex"))
        except (TypeError, ValueError):
            page_index = 0
        page_index = max(0, min(page_index, page_count - 1))

        try:
            page_size = document.pagePointSize(page_index)
            page_width_points = float(page_size.width())
        except Exception:
            return False
        if page_width_points <= 1.0:
            return False

        try:
            ratio = float(root.property("fitWidthRatio"))
        except (TypeError, ValueError):
            ratio = self._DEFAULT_FIT_WIDTH_RATIO
        if not (0.0 < ratio <= 1.0):
            ratio = self._DEFAULT_FIT_WIDTH_RATIO

        scale = float(viewport_width) * ratio / page_width_points
        scale = max(
            self._pdf_view._MIN_ZOOM,
            min(scale, self._pdf_view._MAX_ZOOM),
        )

        root.setProperty("fitPageWidthPoints", page_width_points)
        root.setProperty("fitContentWidthPoints", 0.0)
        root.setProperty("fitContentCenterRatioX", 0.5)
        root.setProperty("zoomScale", float(scale))

        try:
            QMetaObject.invokeMethod(
                root,
                "centerHorizontally",
                Qt.ConnectionType.DirectConnection,
            )
        except (AttributeError, RuntimeError, TypeError):
            pass

        try:
            self._preview._fit_active = False
            self._preview._fit_pending_for_source = False
            self._preview._view_restore_generation += 1
        except Exception:
            pass
        return True

    def _viewport_width(self) -> int:
        try:
            width = int(self._pdf_view.width())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            width = int(self._panel.width())
        return max(width, 0)

    def _document_key(self) -> str | None:
        source_path = getattr(self._preview, "_source_document_path", None)
        if source_path is not None:
            try:
                return str(Path(source_path).resolve())
            except Exception:
                return str(source_path)

        pdf_path = getattr(self._pdf_view, "_fit_document_path", None)
        if pdf_path is not None:
            try:
                return str(Path(pdf_path).resolve())
            except Exception:
                return str(pdf_path)
        return None

    def _remove_redundant_runtime_layers(self) -> None:
        """Remove duplicate Preview/cursor work added by compatibility layers."""
        window = self.parent()
        if window is None:
            return

        # Persian font binding only needs document/tab changes. Connecting it
        # to current_view_changed rehighlighted the whole document on scrolling.
        visual_font_controller = getattr(
            window, "_visual_persian_font_controller", None
        )
        editor_panel = getattr(window, "_editor_panel", None)
        if visual_font_controller is not None and editor_panel is not None:
            try:
                editor_panel.current_view_changed.disconnect(
                    visual_font_controller._on_editor_changed
                )
            except (AttributeError, RuntimeError, TypeError):
                pass

        # The purple SyncTeX caret is intentionally removed. Selection
        # highlighting is the only Preview edit marker.
        overlay = getattr(self._preview, "_nd_preview_caret_overlay", None)
        callback = getattr(self._preview, "_nd_preview_caret_callback", None)
        renderer = getattr(window, "_renderer", None)
        if renderer is not None and callback is not None:
            try:
                renderer.source_position_mapped.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        if overlay is not None:
            timer = getattr(overlay, "_timer", None)
            if timer is not None:
                try:
                    timer.stop()
                except RuntimeError:
                    pass
            try:
                overlay.hide()
                overlay.deleteLater()
            except RuntimeError:
                pass
            self._preview._nd_preview_caret_overlay = None

        controller = getattr(window, "_workspace_interaction_controller", None)
        if controller is None:
            return

        # Late compatibility code used a 25 ms retry timer and a second 55 ms
        # highlight timer. Selection-only sync makes both unnecessary.
        try:
            controller._highlight_timer.stop()
            controller._highlight_timer.timeout.disconnect()
        except (AttributeError, RuntimeError, TypeError):
            pass

        runtime_objects = getattr(window, "_late_runtime_window_object", None)
        if isinstance(runtime_objects, (list, tuple)):
            for item in runtime_objects:
                if isinstance(item, QTimer):
                    try:
                        if item.interval() == 25:
                            item.stop()
                            item.timeout.disconnect()
                    except (RuntimeError, TypeError):
                        pass
                elif (
                    renderer is not None
                    and callable(item)
                    and getattr(item, "__name__", "") == "after_source_mapping"
                ):
                    try:
                        renderer.source_position_mapped.disconnect(item)
                    except (RuntimeError, TypeError):
                        pass

        def set_edit_highlight(preview, text: str) -> None:
            value = str(text or "")
            try:
                preview._pdf_view.set_edit_highlight(value)
                preview._pdf_view._nd_selection_highlight_active = bool(value.strip())
            except (AttributeError, RuntimeError):
                pass

        self._preview.set_edit_highlight = MethodType(
            set_edit_highlight,
            self._preview,
        )

        def set_preview_highlight_text(_controller, text: str = "") -> None:
            value = str(text or "")
            self._preview.set_edit_highlight(value)
            _controller._last_highlight_text = value

        def sync_preview_highlight(_controller) -> None:
            update = getattr(_controller, "_update_preview_selection_highlight", None)
            if callable(update):
                update()

        controller._set_preview_highlight_text = MethodType(
            set_preview_highlight_text,
            controller,
        )
        controller._sync_preview_highlight = MethodType(
            sync_preview_highlight,
            controller,
        )
        controller._update_preview_selection_highlight()

    def _disable_after_manual_zoom(self) -> None:
        if self._auto_enabled:
            self.set_auto_fit(False)
