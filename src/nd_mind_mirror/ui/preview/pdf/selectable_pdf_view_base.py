from pathlib import Path
import time

from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QContextMenuEvent, QImage, QKeySequence, QMouseEvent, QShortcut, QWheelEvent
from PySide6.QtPdf import QPdfDocument
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QApplication, QMenu

from nd_mind_mirror.ui.preview.pdf.pdf_word_selection import word_at_pdf_point


class SelectablePdfView(QQuickWidget):
    view_status_changed = Signal(float, int, int)
    user_zoomed = Signal()
    _MIN_ZOOM = 0.20
    _MAX_ZOOM = 5.00
    _MIN_CONTENT_FIT_FRACTION = 0.20
    _ZOOM_STEP = 1.15

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._reload_token = 0
        self._pan_token = 0
        self._sync_token = 0
        self._fit_token = 0
        self._zoom_token = 0
        self._last_view_status: tuple[float, int, int] | None = None
        self._preview_perf_pdf_started_at = 0.0
        self._preview_perf_pdf_path: Path | None = None
        self._preview_perf_ready_reported = True
        self._is_panning = False
        self._pan_last_position = None
        self._fit_document = QPdfDocument(self)
        self._fit_document_path: Path | None = None
        self._rendered_bounds_cache: dict[
            tuple[str, int], tuple[float, float] | None
        ] = {}
        self.setResizeMode(
            QQuickWidget.ResizeMode.SizeRootObjectToView
        )
        qml_path = Path(__file__).with_name(
            "selectable_pdf_view.qml"
        )
        self.setSource(
            QUrl.fromLocalFile(str(qml_path))
        )
        root = self.rootObject()
        if root is not None:
            root.copyWordRequested.connect(self._copy_selected_word)

        self._copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        self._copy_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._copy_shortcut.activated.connect(self.copy_selection)
        self._copy_context_menu_enabled = False

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(250)
        self._status_timer.timeout.connect(self._poll_view_status)
        self._status_timer.start()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if bool(
            event.modifiers()
            & Qt.KeyboardModifier.ControlModifier
        ):
            delta = event.angleDelta().y()
            if delta == 0:
                delta = event.pixelDelta().y()

            if delta == 0:
                event.accept()
                return

            root = self.rootObject()
            if root is None:
                event.accept()
                return

            try:
                current = float(root.property("zoomScale"))
            except (TypeError, ValueError):
                current = 1.0

            if current <= 0:
                current = 1.0

            # A conventional wheel notch is 120 angle units. Keep the
            # change proportional so high-resolution wheels and touchpads
            # still feel smooth.
            if event.angleDelta().y() != 0:
                steps = delta / 120.0
                factor = self._ZOOM_STEP ** steps
            else:
                factor = (
                    self._ZOOM_STEP
                    if delta > 0
                    else 1.0 / self._ZOOM_STEP
                )

            zoom = max(
                self._MIN_ZOOM,
                min(current * factor, self._MAX_ZOOM),
            )
            # Ask QML to preserve the document point underneath the mouse
            # while the internal PdfMultiPageView is laid out at the new
            # render scale.
            position = event.position()
            root.setProperty("zoomAnchorX", float(position.x()))
            root.setProperty("zoomAnchorY", float(position.y()))
            root.setProperty("zoomTargetScale", float(zoom))
            self._zoom_token += 1
            root.setProperty("zoomToken", self._zoom_token)
            self.user_zoomed.emit()
            QTimer.singleShot(60, self._poll_view_status)
            event.accept()
            return

        super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        middle_pan = (
            event.button()
            == Qt.MouseButton.MiddleButton
        )
        control_left_pan = (
            event.button()
            == Qt.MouseButton.LeftButton
            and bool(
                event.modifiers()
                & Qt.KeyboardModifier.ControlModifier
            )
        )

        if middle_pan or control_left_pan:
            self._is_panning = True
            self._pan_last_position = event.position()
            self.grabMouse()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._clear_word_selection()
            self._set_selection_dragging(True)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # Allow Qt Quick's normal tap recognizers and hyperlinks to receive
        # their events, then select the complete PDF word at the hit position.
        super().mouseDoubleClickEvent(event)
        self._set_selection_dragging(False)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        root = self.rootObject()
        if root is None or self._fit_document.pageCount() <= 0:
            return
        point = event.position()
        root.setProperty("reverseClickX", float(point.x()))
        root.setProperty("reverseClickY", float(point.y()))
        root.mapReverseClick()
        page = int(root.property("reverseClickPage"))
        if page < 0:
            return
        result = word_at_pdf_point(
            self._fit_document, page,
            float(root.property("reverseClickPdfX")),
            float(root.property("reverseClickPdfY")),
        )
        if result is None:
            return
        text, rectangles = result
        root.setProperty("selectedWordPage", page)
        root.setProperty("selectedWordRects", rectangles)
        root.setProperty("selectedWordText", text)
        event.accept()

    @staticmethod
    def _copy_selected_word(text: str) -> None:
        QApplication.clipboard().setText(str(text))

    def selected_text(self) -> str:
        """Return the word selection or the native PDF drag selection."""
        root = self.rootObject()
        if root is None:
            return ""
        word = root.property("selectedWordText")
        if word:
            return str(word)
        active_view = root.property("activeView")
        if active_view is None:
            return ""
        return str(active_view.property("dragSelectedText") or "")

    def copy_selection(self) -> None:
        """Copy the complete selected PDF text through the native clipboard."""
        text = self.selected_text()
        if text:
            QApplication.clipboard().setText(text)

    def enable_copy_context_menu(self) -> None:
        """Expose Copy on independently pinned PDF previews."""
        self._copy_context_menu_enabled = True

    def build_copy_context_menu(self) -> QMenu:
        """Build a menu whose Copy action reads the current PDF selection."""
        menu = QMenu(self)
        action = menu.addAction("Copy")
        action.setEnabled(bool(self.selected_text()))
        action.triggered.connect(self.copy_selection)
        return menu

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        if not self._copy_context_menu_enabled:
            super().contextMenuEvent(event)
            return
        menu = self.build_copy_context_menu()
        menu.exec(event.globalPos())
        event.accept()

    def _clear_word_selection(self) -> None:
        root = self.rootObject()
        if root is not None:
            root.setProperty("selectedWordText", "")
            root.setProperty("selectedWordRects", [])
            root.setProperty("selectedWordPage", -1)

    def _set_selection_dragging(self, value: bool) -> None:
        root = self.rootObject()
        if root is not None:
            root.setProperty("mouseSelectionHeld", bool(value))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._is_panning
            and self._pan_last_position is not None
        ):
            position = event.position()
            delta = position - self._pan_last_position
            self._pan_last_position = position

            root = self.rootObject()
            if root is not None:
                # Drag the document as if it were a sheet of paper: moving
                # the mouse right/down moves the visible content right/down,
                # which means the scroll offsets move left/up.
                root.setProperty(
                    "panDeltaX",
                    float(-delta.x()),
                )
                root.setProperty(
                    "panDeltaY",
                    float(-delta.y()),
                )
                self._pan_token += 1
                root.setProperty(
                    "panToken",
                    self._pan_token,
                )

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._is_panning:
            if event.button() in {
                Qt.MouseButton.MiddleButton,
                Qt.MouseButton.LeftButton,
            }:
                self._is_panning = False
                self._pan_last_position = None
                self.releaseMouse()
                self.unsetCursor()
                event.accept()
                return

        if event.button() == Qt.MouseButton.LeftButton:
            self._set_selection_dragging(False)
        super().mouseReleaseEvent(event)

    def fit_to_panel(self, width_percent: int | float = 95) -> None:
        """Fit the widest rendered text/content span, not the white A4 sheet.

        Qt exposes the full text selection bounds in PDF points.  Using that
        horizontal ink span avoids wasting most of the preview width on the
        paper's left/right margins, which is the behaviour expected from a
        reading-oriented "Fit" action.  Pages without extractable text fall
        back to the complete physical page width.
        """
        root = self.rootObject()
        if root is None:
            return
        ratio = max(0.50, min(float(width_percent) / 100.0, 1.0))
        root.setProperty("fitWidthRatio", ratio)

        page_index = 0
        try:
            page_index = max(int(root.property("currentPageIndex")), 0)
        except (TypeError, ValueError):
            page_index = 0

        page_width_points = 0.0
        content_width_points = 0.0
        content_center_ratio = 0.5
        try:
            page_count = int(self._fit_document.pageCount())
            if page_count > 0:
                page_index = min(page_index, page_count - 1)
                page_size = self._fit_document.pagePointSize(page_index)
                page_width_points = max(float(page_size.width()), 0.0)
                left_points: float | None = None
                right_points: float | None = None

                # Text geometry is exact and cheap.
                selection = self._fit_document.getAllText(page_index)
                if selection.isValid():
                    bounds = selection.boundingRectangle()
                    if bounds.isValid() and bounds.width() > 1.0:
                        left_points = float(bounds.left())
                        right_points = float(bounds.right())

                # Also inspect a low-resolution page render so figures, rules,
                # diagrams and other non-text ink can determine the widest
                # horizontal content. This is only done when the user asks for
                # Fit, not during normal scrolling or live rendering.
                rendered_bounds = self._rendered_ink_x_bounds_points(
                    page_index,
                    float(page_size.width()),
                    float(page_size.height()),
                )
                if rendered_bounds is not None:
                    rendered_left, rendered_right = rendered_bounds
                    left_points = (
                        rendered_left
                        if left_points is None
                        else min(left_points, rendered_left)
                    )
                    right_points = (
                        rendered_right
                        if right_points is None
                        else max(right_points, rendered_right)
                    )

                if (
                    left_points is not None
                    and right_points is not None
                    and right_points - left_points > 1.0
                ):
                    raw_width = right_points - left_points
                    padding = max(2.0, raw_width * 0.01)
                    left_points = max(0.0, left_points - padding)
                    if page_width_points > 0:
                        right_points = min(page_width_points, right_points + padding)
                    else:
                        right_points += padding
                    content_width_points = max(right_points - left_points, 1.0)
                    if page_width_points > 0:
                        content_center_ratio = max(
                            0.0,
                            min(
                                ((left_points + right_points) / 2.0)
                                / page_width_points,
                                1.0,
                            ),
                        )
        except Exception:
            # Fit must never break preview interaction merely because a PDF
            # contains no extractable text or Qt cannot inspect one page.
            pass

        # Sparse or nearly blank pages (for example an accidental first
        # document in a file that contains two standalone documents) can have
        # only a page number or a few glyphs.  Treating that tiny ink span as
        # the fit width can produce absurd scales such as 9405% and make Qt
        # allocate enormous PDF textures.  Fall back to the physical page
        # width whenever the detected content is too narrow to be a useful
        # reading-width target.
        if (
            page_width_points > 0
            and content_width_points > 0
            and content_width_points
            < page_width_points * self._MIN_CONTENT_FIT_FRACTION
        ):
            content_width_points = 0.0
            content_center_ratio = 0.5

        root.setProperty("fitPageWidthPoints", page_width_points)
        root.setProperty("fitContentWidthPoints", content_width_points)
        root.setProperty("fitContentCenterRatioX", content_center_ratio)
        self._fit_token += 1
        root.setProperty("fitToken", self._fit_token)
        QTimer.singleShot(60, self._poll_view_status)

    def _rendered_ink_x_bounds_points(
        self,
        page_index: int,
        page_width_points: float,
        page_height_points: float,
    ) -> tuple[float, float] | None:
        """Estimate horizontal painted-content bounds from a small PDF render."""
        # ND_MIGRATION4_NO_FIT_RASTER_SCAN
        # Auto Fit must never raster-scan pages on the GUI thread.
        return None
        if page_width_points <= 0 or page_height_points <= 0:
            return None
        cache_key = (str(self._fit_document_path or ""), int(page_index))
        if cache_key in self._rendered_bounds_cache:
            return self._rendered_bounds_cache[cache_key]
        try:
            image_width = 640
            image_height = max(
                1,
                int(round(image_width * page_height_points / page_width_points)),
            )
            image = self._fit_document.render(
                int(page_index),
                QSize(image_width, image_height),
            )
            if image.isNull():
                return None
            image = image.convertToFormat(QImage.Format.Format_RGBA8888)
            width = image.width()
            height = image.height()
            if width <= 0 or height <= 0:
                return None

            data = bytes(image.constBits())
            bytes_per_line = image.bytesPerLine()
            min_x = width
            max_x = -1
            # Sampling every second row/pixel is enough to find page-scale ink
            # while keeping Fit essentially instantaneous on ordinary A4 pages.
            for y in range(0, height, 2):
                row_start = y * bytes_per_line
                for x in range(0, width, 2):
                    offset = row_start + x * 4
                    r = data[offset]
                    g = data[offset + 1]
                    b = data[offset + 2]
                    a = data[offset + 3]
                    if a < 8:
                        continue
                    if r < 248 or g < 248 or b < 248:
                        min_x = min(min_x, x)
                        max_x = max(max_x, x)

            if max_x < min_x:
                self._rendered_bounds_cache[cache_key] = None
                return None
            scale = page_width_points / float(width)
            result = (
                min_x * scale,
                min((max_x + 2) * scale, page_width_points),
            )
            self._rendered_bounds_cache[cache_key] = result
            return result
        except Exception:
            self._rendered_bounds_cache[cache_key] = None
            return None

    def set_zoom_percent(self, percent: int | float) -> None:
        root = self.rootObject()
        if root is None:
            return
        value = max(
            self._MIN_ZOOM * 100.0,
            min(float(percent), self._MAX_ZOOM * 100.0),
        )
        root.setProperty("zoomScale", value / 100.0)
        QTimer.singleShot(0, self._poll_view_status)

    def view_status(self) -> tuple[float, int, int]:
        root = self.rootObject()
        if root is None:
            return 100.0, 0, 0
        try:
            zoom = float(root.property("zoomScale")) * 100.0
        except (TypeError, ValueError):
            zoom = 100.0
        if not (zoom > 0.0) or zoom != zoom or zoom == float("inf"):
            zoom = 100.0
        zoom = max(self._MIN_ZOOM * 100.0, min(zoom, self._MAX_ZOOM * 100.0))
        try:
            page_index = int(root.property("currentPageIndex"))
        except (TypeError, ValueError):
            page_index = -1
        try:
            page_count = int(root.property("pageCount"))
        except (TypeError, ValueError):
            page_count = 0
        page_number = page_index + 1 if page_index >= 0 else 0
        return zoom, page_number, max(page_count, 0)

    def _poll_view_status(self) -> None:
        status = self.view_status()
        if (
            not self._preview_perf_ready_reported
            and self._preview_perf_pdf_started_at > 0.0
            and status[2] > 0
        ):
            ready_ms = (time.perf_counter() - self._preview_perf_pdf_started_at) * 1000.0
            print(
                "[preview-perf] qt_pdf_ready "
                f"elapsed_ms={ready_ms:.1f} pages={status[2]} "
                f"path={self._preview_perf_pdf_path}",
                flush=True,
            )
            self._preview_perf_ready_reported = True
        rounded = (round(status[0], 2), status[1], status[2])
        if rounded == self._last_view_status:
            return
        self._last_view_status = rounded
        self.view_status_changed.emit(*status)

    def scroll_to_pdf_location(
        self,
        page: int,
        x: float,
        y: float,
        *,
        keep_horizontal_center: bool = False,
    ) -> None:
        root = self.rootObject()
        if root is None:
            return

        root.setProperty("syncPage", max(int(page), 0))
        root.setProperty("syncX", float(x))
        root.setProperty("syncY", float(y))
        root.setProperty("syncRecenterHorizontal", bool(keep_horizontal_center))
        self._sync_token += 1
        root.setProperty("syncToken", self._sync_token)

    def set_edit_highlight(self, text: str) -> None:
        root = self.rootObject()
        if root is None:
            return
        root.setProperty("editHighlightText", str(text or ""))

    def show_pdf(
        self,
        path: str | Path,
        reset_position: bool = False,
    ) -> bool:
        if self.status() == QQuickWidget.Status.Error:
            return False

        root = self.rootObject()
        if root is None:
            return False

        resolved_path = Path(path).resolve()
        self._preview_perf_pdf_started_at = time.perf_counter()
        self._preview_perf_pdf_path = resolved_path
        self._preview_perf_ready_reported = False
        try:
            pdf_age_ms = max(
                (time.time() - resolved_path.stat().st_mtime) * 1000.0,
                0.0,
            )
        except OSError:
            pdf_age_ms = -1.0
        print(
            "[preview-perf] qt_show_pdf_begin "
            f"pdf_age_ms={pdf_age_ms:.1f} path={resolved_path} "
            f"reset_position={bool(reset_position)}",
            flush=True,
        )
        fit_load_started_at = time.perf_counter()
        if resolved_path != self._fit_document_path:
            try:
                self._fit_document.close()
                self._fit_document.load(str(resolved_path))
                self._fit_document_path = resolved_path
                self._rendered_bounds_cache.clear()
            except Exception:
                self._fit_document_path = None
        fit_load_ms = (time.perf_counter() - fit_load_started_at) * 1000.0
        print(
            "[preview-perf] qt_fit_document_loaded "
            f"elapsed_ms={fit_load_ms:.1f} path={resolved_path}",
            flush=True,
        )

        self._clear_word_selection()
        self._set_selection_dragging(False)
        root.setProperty(
            "resetPositionOnReload",
            bool(reset_position),
        )
        root.setProperty(
            "source",
            QUrl.fromLocalFile(
                str(Path(path).resolve())
            ),
        )
        # Qt Quick PDF can cache an unchanged source URL, so force an
        # explicit document reload for each newly rendered preview.
        self._reload_token += 1
        root.setProperty(
            "reloadToken",
            self._reload_token,
        )
        handoff_ms = (time.perf_counter() - self._preview_perf_pdf_started_at) * 1000.0
        print(
            "[preview-perf] qt_show_pdf_handoff "
            f"elapsed_ms={handoff_ms:.1f} reload_token={self._reload_token} "
            f"path={resolved_path}",
            flush=True,
        )
        QTimer.singleShot(150, self._poll_view_status)
        return True
