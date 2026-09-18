"""Regression tests for Source preview scroll-anchor correction."""

from nd_mind_mirror.ui.editor.latex.source_latex_preview_controller import (
    SourceLatexPreviewController,
)


def test_scroll_anchor_correction_is_idempotent_after_geometry_settles() -> None:
    first = SourceLatexPreviewController._anchored_scroll_value(
        current_value=420,
        anchor_y=12,
        current_y=72,
    )
    assert first == 480

    second = SourceLatexPreviewController._anchored_scroll_value(
        current_value=first,
        anchor_y=12,
        current_y=12,
    )
    assert second == first


def test_scroll_anchor_correction_handles_content_shrinking_above_viewport() -> None:
    corrected = SourceLatexPreviewController._anchored_scroll_value(
        current_value=480,
        anchor_y=60,
        current_y=20,
    )
    assert corrected == 440
