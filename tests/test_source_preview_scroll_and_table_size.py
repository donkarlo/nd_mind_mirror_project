"""Regression coverage for Source preview scrolling and rendered table sizing."""

from pathlib import Path

from nd_mind_mirror.ui.editor.latex.source_latex_preview_size_policy import (
    SourceLatexPreviewSizePolicy,
)
from nd_mind_mirror.ui.editor.latex.source_preview_geometry_index import (
    SourcePreviewGeometryIndex,
)


ROOT = Path(__file__).parent.parent
GRAPHIC_CONTROLLER = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/latex/source_graphic_preview_controller.py"
).read_text(encoding="utf-8")
READABLE_LATEX_CONTROLLER = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/latex/readable_source_latex_preview_controller.py"
).read_text(encoding="utf-8")
GRAPHIC_WIDGET = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/latex/source_graphic_preview_widget.py"
).read_text(encoding="utf-8")
LATEX_WIDGET = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/latex/source_latex_preview_widget.py"
).read_text(encoding="utf-8")
ENHANCED_MAIN_WINDOW = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
).read_text(encoding="utf-8")


def test_geometry_index_limits_scroll_work_to_intersecting_previews() -> None:
    index = SourcePreviewGeometryIndex()
    index.rebuild(
        [(n, n * 100, 80) for n in range(1000)]
    )

    visible = index.candidate_indices(
        scroll_value=50_000,
        viewport_height=900,
    )

    assert visible
    assert len(visible) < 20


def test_table_preview_is_readable_but_bounded_by_viewport() -> None:
    width, height = SourceLatexPreviewSizePolicy.logical_size(
        image_width=1040,
        image_height=400,
        kind="table",
        display=True,
        line_height=20,
        available=900,
    )

    assert 650 <= width <= 864
    assert height == round(width / (1040 / 400))


def test_narrow_table_gets_a_readable_minimum_width() -> None:
    width, _height = SourceLatexPreviewSizePolicy.logical_size(
        image_width=300,
        image_height=180,
        kind="table",
        display=True,
        line_height=20,
        available=900,
    )

    assert width >= round(900 * 0.58)
    assert width <= round(900 * 0.96)


def test_graphic_scroll_hot_path_uses_cached_document_geometry() -> None:
    refresh = GRAPHIC_CONTROLLER.split(
        "    def refresh_positions", 1
    )[1].split("    def _rebuild_layout", 1)[0]

    assert "SourcePreviewGeometryIndex" in GRAPHIC_CONTROLLER
    assert "_SCROLL_REFRESH_MS = 0" in GRAPHIC_CONTROLLER
    assert "document_y" in refresh
    assert "cursorForPosition(" not in refresh
    assert "cursorRect(" not in refresh
    assert "findBlock(" not in refresh
    assert "image_signature=self._image_signatures.get(path)" in refresh


def test_formula_table_scroll_hot_path_uses_cached_document_geometry() -> None:
    refresh = READABLE_LATEX_CONTROLLER.split(
        "    def refresh_positions", 1
    )[1].split("    def _cache_layout_geometry", 1)[0]

    assert "SourcePreviewGeometryIndex" in READABLE_LATEX_CONTROLLER
    assert "_SCROLL_REFRESH_MS = 0" in READABLE_LATEX_CONTROLLER
    assert "document_y" in refresh
    assert "cursorForPosition(" not in refresh
    assert "cursorRect(" not in refresh
    assert "findBlock(" not in refresh


def test_preview_widgets_do_not_raise_on_every_scroll_step() -> None:
    assert "if not self.isVisible():" in GRAPHIC_WIDGET
    assert "if not self.isVisible():" in LATEX_WIDGET
    assert "self.show()\n            self.raise_()" in GRAPHIC_WIDGET
    assert "self.show()\n            self.raise_()" in LATEX_WIDGET


def test_enhanced_window_uses_readable_source_latex_preview_controller() -> None:
    assert "ReadableSourceLatexPreviewController" in ENHANCED_MAIN_WINDOW
    assert (
        "self._source_latex_preview_controller = ReadableSourceLatexPreviewController("
        in ENHANCED_MAIN_WINDOW
    )
