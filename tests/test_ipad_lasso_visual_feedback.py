from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IPAD = ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"
RASTER = (
    IPAD / "Views/Lasso/RasterLassoInteractionController.swift"
).read_text(encoding="utf-8")
FEEDBACK = (
    IPAD / "Views/Lasso/LassoSelectionFeedbackController.swift"
).read_text(encoding="utf-8")
CANVAS = (
    IPAD / "Views/PencilCanvasView.swift"
).read_text(encoding="utf-8")
ACTIVE = (
    IPAD / "Services/ActiveDrawingToolController.swift"
).read_text(encoding="utf-8")
OVERLAY = (
    IPAD / "Views/Lasso/RasterSelectionOverlayView.swift"
).read_text(encoding="utf-8")


def test_one_lasso_controller_owns_mixed_raster_and_pencil_selection() -> None:
    assert "final class RasterLassoInteractionController" in RASTER
    assert "let selectedStrokeIndices: [Int]" in RASTER
    assert "let raster: RasterFragment?" in RASTER
    assert "selectedStrokeIndices(" in RASTER
    assert "makeRasterFragment(" in RASTER
    assert "combinedBounds" in RASTER

    # The old independent PencilCanvas stroke-selection pipeline must be gone.
    assert "SelectionResizeOverlay" not in CANVAS
    assert "handleLassoObservation" not in CANVAS
    assert "selectedStrokeIndices" not in CANVAS
    assert "ResizeSession" not in CANVAS
    assert "MoveSession" not in CANVAS

    assert "LassoDrawingMutationHost" in RASTER
    assert "LassoDrawingMutationHost" in CANVAS
    assert "applyLassoDrawing(" in CANVAS


def test_resize_replaces_selected_strokes_in_place_instead_of_appending_copies() -> None:
    assert "var allStrokes = selection.originalDrawing.strokes" in RASTER
    assert "allStrokes[index] = strokeByApplyingGeometryTransform(" in RASTER
    assert "allStrokes.append" not in RASTER
    assert "selectedDrawing.strokes +" not in RASTER

    # Geometry changes, but visible PencilKit stroke thickness remains unchanged.
    assert "size: point.size" in RASTER
    assert "transform: .identity" in RASTER


def test_mixed_resize_uses_one_common_transform_for_raster_and_strokes() -> None:
    assert "geometryTransform(" in RASTER
    assert "composedDrawing(for: selection)" in RASTER
    assert "composedBackground(for: selection)" in RASTER
    assert "raster.originalBounds" in RASTER
    assert ".applying(transform)" in RASTER
    assert "selection.targetBounds" in RASTER


def test_lasso_feedback_follows_the_unified_raster_selection_overlay() -> None:
    assert "RasterSelectionOverlayView" in FEEDBACK
    assert "SelectionResizeOverlay" not in FEEDBACK
    assert "selectionOverlay?.selectionBounds" in FEEDBACK
    assert "transformedPoints(" in FEEDBACK
    assert "UIColor.systemGray.cgColor" in FEEDBACK
    assert "lineDashPattern" in FEEDBACK


def test_active_tool_routes_completed_lasso_only_to_the_unified_controller() -> None:
    assert "lassoSelectionFeedbackController.onLassoCompleted" in ACTIVE
    assert "rasterLassoInteractionController.selectRasterRegion(with: points)" in ACTIVE


def test_pencil_tap_outside_selection_deselects_without_stealing_handle_taps() -> None:
    assert "UITapGestureRecognizer(" in RASTER
    assert "UITouch.TouchType.pencil.rawValue" in RASTER
    assert "handleOutsideSelectionTap" in RASTER
    assert "overlay.containsSelectionInteraction(at: point)" in RASTER
    assert "clearSelection()" in RASTER
    assert "func containsSelectionInteraction(at point: CGPoint) -> Bool" in OVERLAY
    assert "selectionBounds.contains(point)" in OVERLAY
    assert "moveHandle.point(inside: movePoint, with: nil)" in OVERLAY
    assert "handles.contains" in OVERLAY
