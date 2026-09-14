"""Regression checks for direct iPad TikZ selection, canvas settings, and native colors."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_header_has_canvas_source_options_and_no_manual_render() -> None:
    workspace = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZWorkspaceView.swift"
    )
    assert '"Canvas size…"' in workspace
    assert '"Auto layout"' in workspace
    assert '"Source"' in workspace
    assert "requestTikZRender" not in workspace
    assert 'Image(systemName: "play.fill")' not in workspace


def test_selection_uses_central_single_double_tap_controller() -> None:
    canvas = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZCanvasView.swift"
    )
    coordinator = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZCanvasInteractionCoordinator.swift"
    )
    node = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZNodeView.swift"
    )
    edge = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZEdgeView.swift"
    )
    assert "TikZCanvasInteractionOverlay(" in canvas
    assert "singleTap.require(toFail: doubleTap)" in coordinator
    assert "onNodeSingleTap" in coordinator
    assert "onNodeDoubleTap" in coordinator
    assert "onEdgeSingleTap" in coordinator
    assert "onEdgeDoubleTap" in coordinator
    assert ".highPriorityGesture" not in node
    assert ".highPriorityGesture" not in edge


def test_selected_node_has_separate_move_and_resize_handles() -> None:
    overlay = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZNodeSelectionOverlay.swift"
    )
    assert "ForEach(TikZResizeHandle.allCases)" in overlay
    assert '"arrow.up.and.down.and.arrow.left.and.right"' in overlay
    assert "onMove" in overlay
    assert "onResize" in overlay


def test_native_color_picker_supports_fill_border_line_and_text() -> None:
    toolbar = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZStyleToolbarView.swift"
    )
    color = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Models/TikZ/TikZColorValue.swift"
    )
    source = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/TikZ/TikZSourceEditor.swift"
    )
    assert "ColorPicker(" in toolbar
    assert '"Fill"' in toolbar
    assert '"Border"' in toolbar
    assert '"Text"' in toolbar
    assert '"Line"' in toolbar
    assert "rgb,255:red" in color
    assert 'for: "text"' in source


def test_canvas_defaults_come_from_graphic_tikz_settings() -> None:
    settings = _read(
        "src/nd_mind_mirror/core/settings/defaults/settings.yaml"
    )
    bridge = _read(
        "src/nd_mind_mirror/graphic/tikz/bridge/tikz_canvas_settings.py"
    )
    metadata = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Models/TikZ/TikZCanvasMetadata.swift"
    )
    assert "tikz:" in settings
    assert "canvas_width: 760" in settings
    assert "canvas_height: 980" in settings
    assert 'graphic.get("tikz"' in bridge
    assert "760" in metadata and "980" in metadata


def test_hidden_image_editor_stays_alive_but_is_non_interactive_under_tikz() -> None:
    router = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/GraphicWorkspaceRouterView.swift"
    )
    assert "ContentView()" in router
    assert ".opacity(router.workspace == .image ? 1 : 0)" in router
    assert ".allowsHitTesting(router.workspace == .image)" in router
    assert ".accessibilityHidden(router.workspace != .image)" in router
