"""Draw a preview edit highlight with real vertical padding around the matched text."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import QObject, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtQuick import QQuickItem
from PySide6.QtWidgets import QWidget

from nd_mind_mirror.ui.preview.pdf.selectable_pdf_view import SelectablePdfView


class _PreviewHighlightOverlay(QWidget):
    """Paint the active PDF search result above QQuickWidget with vertical breathing room."""

    _VERTICAL_PADDING_POINTS = 3.0
    _OUTLINE_WIDTH_PX = 2.0
    _OUTLINE_COLOR = QColor("#ff9800")

    def __init__(self, view: SelectablePdfView) -> None:
        super().__init__(view)
        self._view = view
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setGeometry(view.rect())
        self.show()
        self.raise_()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(50)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start()

    def _refresh(self) -> None:
        """Follow preview geometry, scrolling, zooming, and search-result changes."""
        if self.geometry() != self._view.rect():
            self.setGeometry(self._view.rect())
        self.raise_()
        self.update()

    def paintEvent(self, event) -> None:
        del event
        rect = self._current_highlight_rect()
        if rect is None or rect.width() <= 0.0 or rect.height() <= 0.0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(self._OUTLINE_COLOR)
        pen.setWidthF(self._OUTLINE_WIDTH_PX)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        half_pen = self._OUTLINE_WIDTH_PX / 2.0
        painter.drawRoundedRect(
            rect.adjusted(half_pen, half_pen, -half_pen, -half_pen),
            2.5,
            2.5,
        )

    def _current_highlight_rect(self) -> QRectF | None:
        root = self._view.rootObject()
        if not isinstance(root, QQuickItem):
            return None

        objects = [root, *root.findChildren(QObject)]
        search_model = self._find_search_model(objects)
        if search_model is None:
            return None

        try:
            current_page = int(search_model.property("currentPage"))
        except (TypeError, ValueError, RuntimeError):
            return None
        if current_page < 0:
            return None

        bounds = self._search_bounds(search_model)
        if bounds is None:
            return None

        paper = self._find_page_paper(objects, current_page)
        if paper is None:
            return None

        try:
            page_scale = float(paper.property("pageScale"))
        except (TypeError, ValueError, RuntimeError):
            return None
        if not (page_scale > 0.0):
            return None

        padded = QRectF(
            bounds.x(),
            bounds.y() - self._VERTICAL_PADDING_POINTS,
            bounds.width(),
            bounds.height() + 2.0 * self._VERTICAL_PADDING_POINTS,
        )
        scaled = QRectF(
            padded.x() * page_scale,
            padded.y() * page_scale,
            padded.width() * page_scale,
            padded.height() * page_scale,
        )
        try:
            return paper.mapRectToItem(root, scaled)
        except (AttributeError, RuntimeError, TypeError):
            return None

    @staticmethod
    def _find_search_model(objects: Iterable[QObject]) -> QObject | None:
        for item in objects:
            try:
                meta = item.metaObject()
                if (
                    meta.indexOfProperty("currentResultBoundingPolygons") >= 0
                    and meta.indexOfProperty("currentPage") >= 0
                    and meta.indexOfProperty("currentResult") >= 0
                ):
                    return item
            except (AttributeError, RuntimeError, TypeError):
                continue
        return None

    @classmethod
    def _search_bounds(cls, search_model: QObject) -> QRectF | None:
        """Return the current result bounds in PDF points."""
        try:
            polygons = search_model.property("currentResultBoundingPolygons")
        except RuntimeError:
            polygons = None

        points: list[tuple[float, float]] = []
        if polygons:
            try:
                for polygon in polygons:
                    for point in polygon:
                        points.append((float(point.x()), float(point.y())))
            except (AttributeError, TypeError, ValueError):
                points.clear()

        if points:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            left = min(xs)
            right = max(xs)
            top = min(ys)
            bottom = max(ys)
            if right > left and bottom > top:
                return QRectF(left, top, right - left, bottom - top)

        try:
            value = search_model.property("currentResultBoundingRect")
            rect = QRectF(value)
        except (RuntimeError, TypeError):
            return None
        return rect if rect.isValid() and not rect.isEmpty() else None

    @staticmethod
    def _find_page_paper(
        objects: Iterable[QObject],
        page_index: int,
    ) -> QQuickItem | None:
        for item in objects:
            if not isinstance(item, QQuickItem):
                continue
            try:
                meta = item.metaObject()
                if (
                    meta.indexOfProperty("pageScale") < 0
                    or meta.indexOfProperty("pagePointSize") < 0
                ):
                    continue
            except (AttributeError, RuntimeError, TypeError):
                continue

            holder: QQuickItem | None = item.parentItem()
            while holder is not None:
                try:
                    holder_meta = holder.metaObject()
                    if holder_meta.indexOfProperty("index") >= 0:
                        if int(holder.property("index")) == page_index:
                            return item
                        break
                except (AttributeError, RuntimeError, TypeError, ValueError):
                    break
                holder = holder.parentItem()
        return None


class PreviewHighlightController:
    """Replace the thick Qt search outline with a thin padded preview highlight."""

    _installed = False

    @classmethod
    def install(cls) -> None:
        if cls._installed:
            return

        original_init: Callable = SelectablePdfView.__init__
        original_show_pdf: Callable = SelectablePdfView.show_pdf

        def init(view: SelectablePdfView, parent=None) -> None:
            original_init(view, parent)
            cls._attach_overlay(view)
            cls._schedule_style(view)

        def show_pdf(
            view: SelectablePdfView,
            path,
            reset_position: bool = False,
        ) -> bool:
            result = original_show_pdf(
                view,
                path,
                reset_position=reset_position,
            )
            cls._attach_overlay(view)
            cls._schedule_style(view)
            return result

        SelectablePdfView.__init__ = init
        SelectablePdfView.show_pdf = show_pdf
        cls._installed = True

    @staticmethod
    def _attach_overlay(view: SelectablePdfView) -> None:
        overlay = getattr(view, "_nd_preview_highlight_overlay", None)
        if overlay is None:
            view._nd_preview_highlight_overlay = _PreviewHighlightOverlay(view)

    @classmethod
    def _schedule_style(cls, view: SelectablePdfView) -> None:
        QTimer.singleShot(0, lambda item=view: cls._hide_native_outline(item))
        QTimer.singleShot(180, lambda item=view: cls._hide_native_outline(item))

    @staticmethod
    def _hide_native_outline(view: SelectablePdfView) -> None:
        """Keep Qt's own current-result border invisible; the overlay paints it."""
        root = view.rootObject()
        if root is None:
            return

        try:
            objects = [root, *root.findChildren(QObject)]
        except (AttributeError, RuntimeError, TypeError):
            objects = [root]

        for item in objects:
            try:
                meta = item.metaObject()
                if meta.indexOfProperty("currentSearchResultStrokeColor") < 0:
                    continue
                item.setProperty(
                    "currentSearchResultStrokeColor",
                    QColor(0, 0, 0, 0),
                )
                if meta.indexOfProperty("currentSearchResultStrokeWidth") >= 0:
                    item.setProperty("currentSearchResultStrokeWidth", 1.0)
            except (AttributeError, RuntimeError, TypeError):
                continue
