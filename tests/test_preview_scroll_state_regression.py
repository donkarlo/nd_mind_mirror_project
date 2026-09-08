"""Regression checks for page-boundary and multi-page Preview scrolling."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_PREVIEW_DIR = (
    PROJECT_ROOT / "src/nd_mind_mirror/ui/preview/pdf"
)
SCROLL_VIEW = PDF_PREVIEW_DIR / "selectable_pdf_view.qml"
BOUNDARY_VIEW = PDF_PREVIEW_DIR / "SelectablePdfViewBoundary.qml"


def _function_body(source: str, function_name: str) -> str:
    marker = f"function {function_name}("
    start = source.find(marker)
    assert start >= 0, f"{function_name} not found"
    next_function = source.find("\n    function ", start + len(marker))
    timer = source.find("\n    Timer {", start + len(marker))
    candidates = [index for index in (next_function, timer) if index >= 0]
    end = min(candidates) if candidates else len(source)
    return source[start:end]


def test_boundary_geometry_remains_available_for_tight_single_page_previews() -> None:
    source = BOUNDARY_VIEW.read_text(encoding="utf-8")
    assert "function currentPageScrollBounds()" in source
    assert "function clampToCurrentPage()" in source
    assert "function panBy(deltaX, deltaY)" in source
    assert "function setExplicitVerticalPosition(position)" in source


def test_passive_scrollbar_refresh_does_not_clamp_normal_wheel_scrolling() -> None:
    source = SCROLL_VIEW.read_text(encoding="utf-8")
    body = _function_body(source, "updateExplicitScrollBars")
    assert "clampToCurrentPage()" not in body
    assert "currentPageScrollBounds()" in body


def test_live_reload_preserves_page_before_restoring_page_local_offset() -> None:
    source = SCROLL_VIEW.read_text(encoding="utf-8")
    capture = _function_body(source, "captureScrollState")
    restore = _function_body(source, "restoreScrollState")

    assert "savedPageIndex" in capture
    assert "root.currentPageIndex" in capture
    assert "root.syncPage = desiredPage" in restore
    assert "root.syncToken += 1" in restore
    assert "savedPageVerticalRatio" in restore


def test_scroll_view_layers_multi_page_policy_over_boundary_geometry() -> None:
    source = SCROLL_VIEW.read_text(encoding="utf-8")
    assert "SelectablePdfViewBoundary {" in source
