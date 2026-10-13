"""Regression checks for source-backed Pencil geometry and visual TikZ presets."""

from pathlib import Path


PACKAGE = (
    Path(__file__).resolve().parents[1]
    / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"
)


def read(path: str) -> str:
    return (PACKAGE / path).read_text(encoding="utf-8")


def test_all_tikz_tools_are_icon_only_and_presets_have_real_colors() -> None:
    workspace = read("Views/TikZ/TikZWorkspaceView.swift")
    strip = read("Views/TikZ/TikZToolStyleStripView.swift")
    sample = read("Views/TikZ/TikZStyleSampleView.swift")
    store = read("Services/TikZ/TikZStylePresetStore.swift")
    assert 'Label("Styles"' not in workspace
    assert '"Save current style' not in workspace
    assert "savingStyleName" not in workspace
    assert "saveAppearance(_ tool: TikZCanvasTool)" in workspace
    assert "stylePresets.save(" in workspace
    for kind in (
        ".rectangle", ".ellipse", ".triangle",
        ".straightConnector", ".curveConnector", ".polylineConnector",
    ):
        assert kind in strip
    assert "ForEach(presets.filter { $0.tool == tool })" in strip
    assert "onChoosePreset(preset)" in strip
    assert 'Image(systemName: "plus.circle")' in strip
    assert "onDelete(preset.id)" in strip
    assert 'Text("A")' in sample
    assert "nodeStyle.fillColor.color" in sample
    assert "nodeStyle.strokeColor.color" in sample
    assert "nodeStyle.textColor.color" in sample
    assert "edgeStyle.strokeColor.color" in sample
    assert "edgeStyle.linePattern == .dashed" in sample
    assert "UserDefaults.standard" in store


def test_pencil_double_tap_opens_palette_not_label_editor() -> None:
    coordinator = read("Views/TikZ/TikZCanvasInteractionCoordinator.swift")
    overlay = read("Views/TikZ/TikZCanvasInteractionOverlay.swift")
    canvas = read("Views/TikZ/TikZCanvasView.swift")
    palette = read("Views/TikZ/TikZPencilToolPaletteView.swift")
    assert "#selector(handlePencilDoubleTap(_:))" in coordinator
    assert "pencilDoubleTap.numberOfTapsRequired = 2" in coordinator
    assert "UITouch.TouchType.pencil.rawValue" in coordinator
    assert "singleTap.require(toFail: pencilDoubleTap)" in coordinator
    assert "onPencilDoubleTap?(recognizer.location(in: view))" in coordinator
    assert "onPencilDoubleTap: onPencilDoubleTap" in overlay
    assert "pencilPalettePoint = point" in canvas
    assert "TikZPencilToolPaletteView(" in canvas
    assert "TikZToolStyleStripView(" in palette
    assert "onDismiss" in palette


def test_freehand_recognition_runs_with_no_explicit_shape_tool() -> None:
    coordinator = read("Views/TikZ/TikZCanvasInteractionCoordinator.swift")
    recognizer = read("Services/TikZ/TikZPencilShapeRecognizer.swift")
    overlay = read("Views/TikZ/TikZCanvasInteractionOverlay.swift")
    canvas = read("Views/TikZ/TikZCanvasView.swift")
    workspace = read("Views/TikZ/TikZWorkspaceView.swift")

    assert "shapePan?.isEnabled = true" in coordinator
    assert "guard let shape = activeTool.nodeShape" not in coordinator
    assert "pencilShapeRecognizer.recognize(samples)" in coordinator
    assert "onPencilShapeRecognized?(recognized.shape, recognized.bounds)" in coordinator
    assert "onPencilShapeRecognized: onPencilShapeRecognized" in overlay
    assert "onPencilTraceChanged: onPencilTraceChanged" in overlay
    assert "onPencilTraceChanged?(shapeSamples)" in coordinator
    assert "onPencilTraceChanged?([])" in coordinator
    assert "path.addLines(pencilTrace)" in canvas
    assert "onPencilShapeRecognized: { shape, bounds in" in canvas
    assert "onShapeCreate(" in canvas
    assert "TikZSourceEditor.addNode(" in workspace
    assert "editingNodeName = created?.name" in workspace

    assert "samples.count >= 12" in recognizer
    assert "bounds.width >= 28, bounds.height >= 28" in recognizer
    assert "ellipseError <" in recognizer
    assert "shape: .ellipse" in recognizer
    assert "cornerCount == 3" in recognizer and "cornerCount >= 6" in recognizer
    assert "shapePan?.isEnabled = activeTool.nodeShape != nil" not in coordinator


def test_existing_nodes_and_connectors_are_not_consumed_by_freehand_recognition() -> None:
    coordinator = read("Views/TikZ/TikZCanvasInteractionCoordinator.swift")
    assert "hitTester.target(at: point, in: graph, canvasSize: canvasSize) == nil" in coordinator
    assert "connectionGeometry.nearest(" in coordinator
    assert "onConnectorDragEnded?(sourceName, target?.node.name, point)" in coordinator
    assert "onNodeSingleTap?(name)" in coordinator
    assert "onNodeDoubleTap?(name)" in coordinator
