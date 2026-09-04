from pathlib import Path


def _project_file(relative: str) -> Path:
    return Path(__file__).resolve().parent.parent / relative


def test_custom_lasso_draws_gray_dashed_feedback_without_native_lasso() -> None:
    feedback = _project_file(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/Lasso/"
        "LassoSelectionFeedbackController.swift"
    ).read_text(encoding="utf-8")
    controller = _project_file(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/"
        "ActiveDrawingToolController.swift"
    ).read_text(encoding="utf-8")
    canvas = _project_file(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/"
        "PencilCanvasView.swift"
    ).read_text(encoding="utf-8")

    assert "final class LassoSelectionFeedbackController" in feedback
    assert "UIColor.systemGray.cgColor" in feedback
    assert "lineDashPattern" in feedback
    assert "UITouch.TouchType.pencil.rawValue" in feedback
    assert "render(points: freehandPoints, closed: false)" in feedback
    assert "render(points: completedPoints, closed: true)" in feedback
    assert "transformedPoints(" in feedback
    assert "SelectionResizeOverlay" in feedback

    assert "LassoSelectionFeedbackController()" in controller
    assert "lassoSelectionFeedbackController.attach(to: canvas)" in controller
    assert "lassoSelectionFeedbackController.setEnabled(state.kind == .lasso)" in controller
    assert "let shouldEnableNativeDrawing = kind != .lasso" in controller
    assert "PKLassoTool(" not in controller

    assert "handleLassoObservation" in canvas
    assert "updateSelectionFromLasso(canvas.drawing)" in canvas
