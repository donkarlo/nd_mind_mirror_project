"""Regression checks for generation-isolated Qt Quick PDF handoff."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_PREVIEW = (
    PROJECT_ROOT
    / "src"
    / "nd_mind_mirror"
    / "ui"
    / "preview"
    / "pdf"
)
WRAPPER_QML = PDF_PREVIEW / "selectable_pdf_view.qml"
GENERATION_QML = PDF_PREVIEW / "SelectablePdfGenerationView.qml"
SELECTABLE_PY = PDF_PREVIEW / "selectable_pdf_view.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_each_pdf_generation_uses_a_fresh_view_instance() -> None:
    source = _source(WRAPPER_QML)

    assert "SelectablePdfGenerationView" in source
    assert source.count("Loader {") == 2
    assert "loader.active = false" in source
    assert "recreateInactiveSlot.restart()" in source
    assert "pdfDocument.source" not in source


def test_old_generation_stays_active_until_new_document_is_ready() -> None:
    source = _source(WRAPPER_QML)

    ready_check = (
        "!view || !view.documentIsReady() || view.pageCount <= 0"
    )
    assert ready_check in source
    assert "root.activeSlot = root.loadingSlot" in source
    assert "visible: root.activeSlot === 0" in source
    assert "visible: root.activeSlot === 1" in source


def test_intermediate_generations_collapse_without_reloading_active_pdf() -> None:
    source = _source(WRAPPER_QML)

    assert "root.requestedToken = root.reloadToken" in source
    assert source.count("root.loadingToken !== root.requestedToken") >= 2
    assert "Qt.callLater(root.beginLatestGeneration)" in source
    assert "root.pageCount = 0" in source
    assert "generationPending" in source


def test_generation_view_keeps_existing_scroll_restore_behavior() -> None:
    source = _source(GENERATION_QML)

    assert "function captureScrollState()" in source
    assert "function restoreScrollState()" in source
    assert "pageRestoreRetry" in source


def test_native_fit_document_is_closed_with_the_widget() -> None:
    source = _source(SELECTABLE_PY)

    assert "def closeEvent" in source
    assert "self._status_timer.stop()" in source
    assert "self._fit_document.close()" in source
