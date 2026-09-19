"""Regression coverage for geometry-cached Source preview scrolling."""

from nd_mind_mirror.ui.editor.latex.source_preview_geometry_index import (
    SourcePreviewGeometryIndex,
)


def test_geometry_index_returns_only_overlays_that_can_intersect_viewport() -> None:
    index = SourcePreviewGeometryIndex()
    index.rebuild(
        [
            (0, 100, 120),
            (1, 500, 80),
            (2, 900, 200),
            (3, 1500, 100),
        ]
    )

    assert index.candidate_indices(760, 300) == (2,)


def test_geometry_index_includes_tall_preview_started_above_viewport() -> None:
    index = SourcePreviewGeometryIndex()
    index.rebuild(
        [
            (0, 300, 500),
            (1, 1000, 80),
        ]
    )

    assert index.candidate_indices(700, 200) == (0,)
