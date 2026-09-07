from pathlib import Path

from PySide6.QtCore import QMetaObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QLabel,
    QStackedWidget,
    QVBoxLayout,
)

from nd_mind_mirror.ui.preview.base.preview import Preview
from nd_mind_mirror.ui.preview.pdf.pdf_handoff_coalescer import (
    PdfHandoffCoalescer,
)
from nd_mind_mirror.ui.preview.pdf.selectable_pdf_view import (
    SelectablePdfView,
)


class LatexPreview(Preview):
    view_status_changed = Signal(float, int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setMinimumWidth(0)
        self._current_pdf_path: Path | None = None
        self._source_document_path: Path | None = None
        self._reset_position_on_next_pdf = True
        self._has_success_for_current_source = False
        self._last_error = ""
        self._default_zoom_percent = 100.0
        self._auto_fit_on_open = True
        self._fit_width_percent = 95
        # Fit is computed once for a source. Live PDF reloads preserve that
        # exact scale and scroll position rather than recalculating content width.
        self._fit_active = True
        self._fit_pending_for_source = True
        self._view_restore_generation = 0

        self._pdf_view = SelectablePdfView(self)
        self._pdf_view.view_status_changed.connect(
            self.view_status_changed.emit
        )
        self._pdf_view.user_zoomed.connect(
            self._leave_fit_mode
        )
        self._pdf_view.setMinimumWidth(0)

        # Qt Quick PdfDocument is native code and is sensitive to repeated
        # source detach/attach cycles arriving faster than the previous load.
        # Keep the first handoff immediate while collapsing a typing burst to
        # the newest generated PDF.
        self._pdf_handoff_coalescer = PdfHandoffCoalescer(
            minimum_interval_ms=180,
            parent=self,
        )
        self._pdf_handoff_coalescer.handoff_requested.connect(
            self._present_pdf_now
        )

        self._message = QLabel(
            "Open a .tex file to render its preview.",
            self,
        )
        self._message.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )
        self._message.setWordWrap(True)
        self._message.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._message.setMargin(12)

        self._stack = QStackedWidget(self)
        self._stack.setMinimumWidth(0)
        self._stack.addWidget(self._message)
        self._stack.addWidget(self._pdf_view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    @property
    def current_pdf_path(self) -> Path | None:
        return self._current_pdf_path

    def set_default_zoom_percent(
        self,
        percent: int | float,
    ) -> None:
        value = max(20.0, min(float(percent), 500.0))
        self._default_zoom_percent = value
        if self._current_pdf_path is not None and not self._fit_active:
            self._pdf_view.set_zoom_percent(value)

    def configure_initial_view(
        self,
        auto_fit_on_open: bool,
        fit_width_percent: int | float,
    ) -> None:
        self._auto_fit_on_open = bool(auto_fit_on_open)
        self._fit_width_percent = max(50, min(int(fit_width_percent), 100))

    def set_source_document(
        self,
        path: str | Path,
    ) -> None:
        source_path = Path(path).expanduser().resolve()
        if source_path == self._source_document_path:
            return

        self._pdf_handoff_coalescer.cancel_pending()
        self._source_document_path = source_path
        self._reset_position_on_next_pdf = True
        self._fit_active = self._auto_fit_on_open
        self._fit_pending_for_source = self._auto_fit_on_open
        self._has_success_for_current_source = False
        self._current_pdf_path = None
        self._last_error = ""
        self._view_restore_generation += 1

    def show_pdf(self, path: str) -> None:
        pdf_path = Path(path).resolve()

        if not pdf_path.is_file():
            self._pdf_handoff_coalescer.cancel_pending()
            self._current_pdf_path = None
            self.show_error(
                f"Generated PDF does not exist: {pdf_path}"
            )
            return

        reset_position = self._reset_position_on_next_pdf
        self._pdf_handoff_coalescer.request(
            pdf_path,
            reset_position,
        )

    def _present_pdf_now(
        self,
        pdf_path: Path,
        reset_position: bool,
    ) -> None:
        """Perform the actual Qt Quick PDF handoff after burst coalescing."""
        if not pdf_path.is_file():
            return

        # Once Fit has been established, remember its exact zoom before each
        # live reload. Qt Quick PDF can temporarily expose its default 100%
        # scale while the document source is being replaced; reasserting the
        # same saved scale prevents the visible half-page-width flash.
        stable_zoom_percent: float | None = None
        preserve_live_view = self._fit_active and not self._fit_pending_for_source
        if preserve_live_view:
            stable_zoom_percent = self._pdf_view.view_status()[0]

        if not self._pdf_view.show_pdf(
            pdf_path,
            reset_position=bool(reset_position),
        ):
            self._current_pdf_path = None
            self.show_error(
                "Could not initialize the selectable Qt Quick PDF preview. "
                "PySide6/Qt 6.8 or newer is required."
            )
            return

        if self._fit_active and self._fit_pending_for_source:
            # Fit exactly once after the first PDF for a newly opened source.
            # Later keystroke-driven PDF reloads keep this scale unchanged.
            self._fit_pending_for_source = False
            QTimer.singleShot(260, self._apply_fit_without_mode_change)
        elif reset_position:
            self._pdf_view.set_zoom_percent(
                self._default_zoom_percent
            )
        elif stable_zoom_percent is not None:
            self._schedule_live_view_restore(stable_zoom_percent)

        self._reset_position_on_next_pdf = False
        self._current_pdf_path = pdf_path
        self._has_success_for_current_source = True
        self._last_error = ""
        self._pdf_view.setToolTip("")
        self._stack.setCurrentWidget(
            self._pdf_view
        )

    def fit_to_panel(self) -> None:
        if self._current_pdf_path is None:
            return
        self._fit_active = True
        self._fit_pending_for_source = False
        self._view_restore_generation += 1
        self._pdf_view.fit_to_panel(self._fit_width_percent)

    def _apply_fit_without_mode_change(self) -> None:
        if self._current_pdf_path is None or not self._fit_active:
            return
        self._view_restore_generation += 1
        self._pdf_view.fit_to_panel(self._fit_width_percent)

    def _schedule_live_view_restore(self, zoom_percent: float) -> None:
        """Hold a fitted zoom/scroll steady while Qt reloads the generated PDF."""
        self._view_restore_generation += 1
        generation = self._view_restore_generation
        for delay_ms in (0, 30, 80, 160, 300, 500):
            QTimer.singleShot(
                delay_ms,
                lambda value=zoom_percent, token=generation: self._restore_live_view(
                    value,
                    token,
                ),
            )

    def _restore_live_view(self, zoom_percent: float, generation: int) -> None:
        if (
            generation != self._view_restore_generation
            or not self._fit_active
            or self._current_pdf_path is None
        ):
            return

        self._pdf_view.set_zoom_percent(zoom_percent)
        root = self._pdf_view.rootObject()
        if root is None:
            return
        try:
            QMetaObject.invokeMethod(root, "restoreScrollState")
        except (RuntimeError, TypeError):
            pass

    def _leave_fit_mode(self) -> None:
        self._fit_active = False
        self._fit_pending_for_source = False
        self._view_restore_generation += 1

    def set_zoom_percent(self, percent: int | float) -> None:
        if self._current_pdf_path is None:
            return
        self._fit_active = False
        self._fit_pending_for_source = False
        self._view_restore_generation += 1
        self._pdf_view.set_zoom_percent(percent)

    def scroll_to_source_location(
        self,
        page: int,
        x: float,
        y: float,
    ) -> None:
        if self._current_pdf_path is None:
            return
        self._pdf_view.scroll_to_pdf_location(
            page,
            x,
            y,
            keep_horizontal_center=self._fit_active,
        )

    def set_edit_highlight(self, text: str) -> None:
        self._pdf_view.set_edit_highlight(text)

    def show_error(self, message: str) -> None:
        # A compile failure is newer than any queued successful generation.
        # Cancel that queued generation so Preview never advances to stale PDF
        # content after the diagnostic tree is already showing the new error.
        self._pdf_handoff_coalescer.cancel_pending()
        self._last_error = str(message)
        if (
            self._has_success_for_current_source
            and self._current_pdf_path is not None
        ):
            # A partially typed LaTeX command can make one live compile fail.
            # Do not destroy a useful preview that was rendered successfully
            # moments earlier; the next valid generation will replace it.
            self._pdf_view.setToolTip(self._last_error)
            self._stack.setCurrentWidget(self._pdf_view)
            return

        self._message.setText(self._last_error)
        self._stack.setCurrentWidget(
            self._message
        )

    def show_message(self, message: str) -> None:
        self._pdf_handoff_coalescer.cancel_pending()
        self._message.setText(message)
        self._stack.setCurrentWidget(
            self._message
        )
