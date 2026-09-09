"""Regression checks for Qt Quick PDF lifecycle-safe preview reloads."""

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
BASE_QML = PDF_PREVIEW / "SelectablePdfViewBase.qml"
SELECTABLE_QML = PDF_PREVIEW / "selectable_pdf_view.qml"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_reload_never_detaches_pdf_document_to_empty_source() -> None:
    source = _source(BASE_QML)
    assert 'pdfDocument.source = ""' not in source
    assert "pdfDocument.source = target" in source


def test_reload_waits_for_native_pdf_lifecycle() -> None:
    source = _source(BASE_QML)
    assert "PdfDocument.Loading" in source
    assert "PdfDocument.Unloading" in source
    assert "documentReloadPending" in source
    assert "documentReloadDispatch" in source


def test_reload_collapses_to_latest_pending_source() -> None:
    source = _source(BASE_QML)
    assert "root.pendingDocumentSource = root.source" in source
    assert "var target = root.pendingDocumentSource" in source
    assert "root.documentReloadPending = false" in source


def test_scroll_restore_requires_ready_pdf_document() -> None:
    base_source = _source(BASE_QML)
    selectable_source = _source(SELECTABLE_QML)
    assert "if (!root.documentIsReady())" in base_source
    assert (
        "if (!root.documentIsReady() || !root.restorePositionPending)"
        in selectable_source
    )


def test_repeated_page_restore_does_not_run_during_loading() -> None:
    source = _source(SELECTABLE_QML)
    assert "if (root.documentIsReady())\n                root.restoreScrollState()" in source
