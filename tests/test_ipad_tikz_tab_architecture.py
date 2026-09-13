"""Regression checks for the isolated Image/TikZ iPad workspace architecture."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IPAD = ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"
TIKZ = ROOT / "src/nd_mind_mirror/graphic/tikz"
MAIN = ROOT / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"


def test_image_editor_remains_the_first_existing_content_view_tab() -> None:
    tabs = (IPAD / "Views/GraphicWorkspaceTabsView.swift").read_text(encoding="utf-8")
    image_editor = (IPAD / "Views/ContentView.swift").read_text(encoding="utf-8")
    assert "ContentView()" in tabs
    assert 'Label("Image"' in tabs
    assert "@StateObject private var bridge = GraphicBridgeClient()" in image_editor
    assert "PencilCanvasView(" in image_editor


def test_tikz_tab_supports_requested_graph_operations() -> None:
    workspace = (IPAD / "Views/TikZ/TikZWorkspaceView.swift").read_text(encoding="utf-8")
    editor = (IPAD / "Services/TikZ/TikZSourceEditor.swift").read_text(encoding="utf-8")
    layout = (IPAD / "Services/TikZ/TikZAutoLayoutService.swift").read_text(encoding="utf-8")
    assert 'Label("TikZ"' in (IPAD / "Views/GraphicWorkspaceTabsView.swift").read_text(encoding="utf-8")
    assert "moveNode(" in editor
    assert "addEdge(" in editor
    assert "updateEdgeLabel(" in editor
    assert "addNode(shape:" in editor
    assert "autoLayout()" in workspace
    assert "isAddingEdge" in workspace
    assert "positions(for graph:" in layout


def test_desktop_starts_tikz_bridge_separately_from_raster_bridge() -> None:
    main = MAIN.read_text(encoding="utf-8")
    controller = (TIKZ / "tikz_bridge_session_controller.py").read_text(encoding="utf-8")
    assert "TikZBridgeSessionController(" in main
    assert "TikZBridgeServer(" in controller
    assert "Thread(" in controller
    assert "8765" in controller


def test_tikz_workspace_saves_real_source_atomically() -> None:
    workspace = (TIKZ / "bridge/workspace.py").read_text(encoding="utf-8")
    assert '"\\\\begin{tikzpicture}"' in workspace
    assert "write_atomic" in workspace
    assert "os.replace(temp, path)" in workspace
