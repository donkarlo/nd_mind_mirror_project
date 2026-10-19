"""Real Qt PDF mouse selection, copy, and independent preview regression tests."""

from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QFont, QMouseEvent, QPainter, QPdfWriter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from nd_mind_mirror.ui.preview.pdf.pdf_word_selection import word_at_pdf_point
from nd_mind_mirror.ui.preview.pdf.selectable_pdf_view import SelectablePdfView
from nd_mind_mirror.ui.window.main.preview.pinned_pdf_preview_window import (
    PinnedPdfPreviewWindow,
)


def _app():
    return QApplication.instance() or QApplication([])


def _make_pdf(path: Path, text: str):
    writer = QPdfWriter(str(path))
    painter = QPainter(writer)
    painter.setFont(QFont("Helvetica", 18))
    painter.drawText(400, 400, text)
    painter.end()


def _ready(widget: SelectablePdfView):
    app = _app()
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        app.processEvents()
        root = widget.rootObject()
        if root is not None and int(root.property("pageCount") or 0) >= 1:
            # Qt reports pageCount before PdfMultiPageView has instantiated
            # and laid out its actual paper delegate. Wait for hit testing.
            for _ in range(45):
                app.processEvents()
                time.sleep(0.015)
            return root
        time.sleep(0.015)
    raise AssertionError("The preview did not load in time")


def _pdf_hit(root, pdf_x=60.0, pdf_y=29.0):
    """Find the viewport coordinates of a glyph without relying on screen DPI."""
    best = None
    for y in range(20, 145, 10):
        for x in range(80, 330, 10):
            root.setProperty("reverseClickX", float(x))
            root.setProperty("reverseClickY", float(y))
            root.mapReverseClick()
            if root.property("reverseClickPage") != 0:
                continue
            px = float(root.property("reverseClickPdfX"))
            py = float(root.property("reverseClickPdfY"))
            distance = (px-pdf_x)**2 + (py-pdf_y)**2
            if best is None or distance < best[0]:
                best = distance, QPoint(x, y)
    assert best is not None and best[0] < 250, "Could not locate sample PDF text"
    return best[1]


def test_double_click_selects_complete_word_and_ctrl_c_copies_it(tmp_path):
    app = _app()
    file = tmp_path / "selection.pdf"
    _make_pdf(file, "Example selection function")
    view = SelectablePdfView()
    try:
        view.resize(820, 880)
        view.show()
        assert view.show_pdf(file)
        root = _ready(view)
        point = _pdf_hit(root)
        QTest.mouseDClick(view, Qt.MouseButton.LeftButton, pos=point)
        app.processEvents()
        assert root.property("selectedWordText") == "Example"
        assert root.property("selectedWordPage") == 0
        assert len(root.property("selectedWordRects")) >= 1
        QTest.keyClick(view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        app.processEvents()
        assert app.clipboard().text() == "Example"
    finally:
        view.close()


def test_mouse_drag_selects_text_without_panning_the_pdf(tmp_path):
    app = _app()
    file = tmp_path / "drag.pdf"
    _make_pdf(file, "Example selection function")
    view = SelectablePdfView()
    try:
        view.resize(820, 880)
        view.show()
        assert view.show_pdf(file)
        root = _ready(view)
        start = _pdf_hit(root, 39.0, 29.0)
        finish = _pdf_hit(root, 166.0, 29.0)
        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=start)
        for x in range(start.x() + 4, finish.x() + 1, 9):
            move = QMouseEvent(
                QEvent.Type.MouseMove, QPointF(x, start.y()),
                QPointF(x, start.y()), Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
            )
            QApplication.sendEvent(view, move)
            app.processEvents()
            time.sleep(0.003)
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=finish)
        for _ in range(10):
            app.processEvents()
            time.sleep(0.005)
        active = root.property("activeView")
        assert "Example" in active.property("dragSelectedText")
        assert root.property("mouseSelectionHeld") is False
        assert view._is_panning is False
        QTest.keyClick(view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        app.processEvents()
        assert "Example" in app.clipboard().text()
    finally:
        view.close()


def test_multiple_pinned_windows_survive_other_preview_closing(tmp_path):
    _app()
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    _make_pdf(first, "First document")
    _make_pdf(second, "Second document")
    windows = [PinnedPdfPreviewWindow(first, "First"),
               PinnedPdfPreviewWindow(second, "Second")]
    try:
        for window in windows:
            assert window._snapshot.exists()
            assert window._viewer._fit_document.pageCount() == 1
        assert "First" in windows[0]._viewer._fit_document.getAllText(0).text()
        assert "Second" in windows[1]._viewer._fit_document.getAllText(0).text()
        windows[0].close()
        assert not windows[0]._snapshot.exists()
        assert windows[1]._snapshot.exists()
        assert "Second" in windows[1]._viewer._fit_document.getAllText(0).text()
    finally:
        for window in windows:
            window.close()


def test_unicode_word_boundaries_are_not_ascii_only(tmp_path):
    _app()
    file = tmp_path / "unicode.pdf"
    _make_pdf(file, "Mädchen Überprüfung")
    from PySide6.QtPdf import QPdfDocument
    doc = QPdfDocument()
    doc.load(str(file))
    full = doc.getAllText(0)
    assert "Mädchen" in full.text()
    first = doc.getSelectionAtIndex(0, 2, 1).boundingRectangle()
    point = first.center()
    result = word_at_pdf_point(doc, 0, point.x(), point.y())
    assert result is not None and result[0] == "Mädchen"
    doc.close()


def test_pinned_preview_copies_selected_word_and_shows_copy_menu(tmp_path):
    app = _app()
    pdf = tmp_path / "copy.pdf"
    _make_pdf(pdf, "Example pinned selection")
    window = PinnedPdfPreviewWindow(pdf, "Copy")
    try:
        window.show()
        root = _ready(window._viewer)
        point = _pdf_hit(root)
        QTest.mouseDClick(window._viewer, Qt.MouseButton.LeftButton, pos=point)
        app.processEvents()
        assert window._viewer.selected_text() == "Example"
        window._viewer.setFocus()
        app.clipboard().setText("previous value")
        QTest.keyClick(window._viewer, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        app.processEvents()
        assert app.clipboard().text() == "Example"

        menu = window._viewer.build_copy_context_menu()
        assert [action.text() for action in menu.actions()] == ["Copy"]
        assert menu.actions()[0].isEnabled()
        app.clipboard().setText("previous value")
        menu.actions()[0].trigger()
        assert app.clipboard().text() == "Example"
    finally:
        window.close()


def test_pinned_preview_ctrl_f_has_independent_search(tmp_path):
    app = _app()
    one = tmp_path / "one.pdf"
    two = tmp_path / "two.pdf"
    _make_pdf(one, "Example Example")
    _make_pdf(two, "Other wording")
    first = PinnedPdfPreviewWindow(one, "One")
    second = PinnedPdfPreviewWindow(two, "Two")
    try:
        first.show()
        _ready(first._viewer)
        first._viewer.setFocus()
        QTest.keyClick(first._viewer, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
        app.processEvents()
        assert first._find_controller._bar.isVisible()
        second.show()
        _ready(second._viewer)
        first._find_controller._input.setText("Example")
        app.processEvents()
        assert first._find_controller._status.text() == "1/2"
        assert first._viewer.rootObject().property("findQuery") == "Example"
        first._find_controller.next()
        assert first._find_controller._status.text() == "2/2"
        first._find_controller.previous()
        assert first._find_controller._status.text() == "1/2"
        assert second._viewer.rootObject().property("findQuery") == ""
        first._find_controller.hide()
        assert first._viewer.rootObject().property("findQuery") == ""
        assert not first._find_controller._bar.isVisible()
    finally:
        first.close()
        second.close()
