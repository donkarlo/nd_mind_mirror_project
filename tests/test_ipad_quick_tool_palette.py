from pathlib import Path


def test_ipad_pencil_double_tap_quick_tool_palette_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    package = root / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"

    gesture = (
        package / "Services/PencilQuickToolPaletteGestureController.swift"
    ).read_text(encoding="utf-8")
    history = (
        package / "Services/CanvasEditHistoryController.swift"
    ).read_text(encoding="utf-8")
    active_tool = (
        package / "Services/ActiveDrawingToolController.swift"
    ).read_text(encoding="utf-8")
    footprint_validator = (
        package / "Services/PencilQuickToolTapFootprintValidator.swift"
    ).read_text(encoding="utf-8")
    palette = (
        package / "Views/QuickDrawingToolPaletteView.swift"
    ).read_text(encoding="utf-8")
    canvas = (package / "Views/PencilCanvasView.swift").read_text(encoding="utf-8")
    content = (package / "Views/ContentView.swift").read_text(encoding="utf-8")

    assert not (package / "Services/PencilTapGestureRecognizer.swift").exists()
    assert "UITapGestureRecognizer" in gesture
    assert "doubleTap.numberOfTapsRequired = 2" in gesture
    assert "dismissTap.numberOfTapsRequired = 1" in gesture
    assert "UITouch.TouchType.pencil" in gesture
    assert "maximumInterTapInterval: TimeInterval = 0.35" in gesture
    assert "maximumInterTapDistance: CGFloat = 12" in gesture
    assert "shouldReceive touch: UITouch" in gesture
    assert "touch.tapCount <= 1" in gesture
    assert "secondTapTimestamp - firstTapTimestamp" in gesture
    assert "shouldRecognizeSimultaneouslyWith" in gesture
    assert "cancelsTouchesInView = false" in gesture
    assert "guard palettePresented != presented else" in gesture
    assert "doubleTapGesture?.isEnabled = !presented" in gesture
    assert "dismissTapGesture?.isEnabled = presented" in gesture
    assert "dismissTap.require(toFail: doubleTap)" not in gesture
    assert "onPencilContactBegan" in gesture
    assert "onDoubleTapRejected" in gesture

    assert "makeCheckpoint()" in history
    assert "restoreCheckpoint" in history
    assert "quickToolTapCheckpoint = historyController?.makeCheckpoint()" in active_tool
    assert "quickToolTapStartingDrawing = canvas?.drawing" in active_tool
    assert "PencilQuickToolTapFootprintValidator()" in active_tool
    assert "isTapLikeChange" in active_tool
    assert "restoreQuickToolTapCandidate" in active_tool
    assert "restoreQuickToolDismissalTapCandidate" in active_tool
    assert "discardQuickToolTapCandidate" in active_tool
    assert "maximumAddedStrokeCount = 2" in footprint_validator
    assert "minimumStrokeSpan: CGFloat = 10" in footprint_validator
    assert "stroke.renderBounds" in footprint_validator

    assert "quickToolGestureController.attach(" in canvas
    assert "to: content" in canvas
    assert "coordinateView: scroll" in canvas
    assert "setPalettePresented" in canvas
    assert "configureQuickToolGestures" in canvas
    assert "quickToolGestureController.onPencilContactBegan" in canvas
    assert "controller?.beginQuickToolTapCandidate()" in canvas
    assert "quickToolGestureController.onDoubleTapRejected" in canvas
    assert "onSinglePencilTap(point)" in canvas
    assert "restoreQuickToolDismissalTapCandidate" in canvas
    assert "guard controller?.restoreQuickToolTapCandidate() == true else" in canvas
    assert "quickToolPalettePresented" in canvas

    assert "columnCount = 4" in palette
    assert "maximumVisibleRows = 4" in palette
    assert "savedTools.tools" in palette
    assert 'image: "lasso"' in palette
    assert 'image: "photo.badge.plus"' in palette
    assert "preferredAboveY = anchor.y - pencilGap - halfHeight" in palette
    assert "containerSize.width - halfWidth - edgeMargin" in palette
    assert "containerSize.height - halfHeight - edgeMargin" in palette

    assert "quickToolPaletteAnchor = point" in content
    assert "quickToolPaletteAnchor = nil" in content
    assert "onSelectSavedTool: selectQuickTool" in content
    assert "onSelectLasso: selectQuickLasso" in content
