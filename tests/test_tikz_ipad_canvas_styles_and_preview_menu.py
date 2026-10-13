"""Regression checks for iPad canvas styling and desktop TikZ editing."""

from pathlib import Path

from nd_mind_mirror.graphic.tikz.tikz_document_manager import TikZDocumentManager


ROOT = Path(__file__).resolve().parents[1]
SWIFT = ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"


def read(relative: str) -> str:
    return (SWIFT / relative).read_text(encoding="utf-8")


def test_existing_tikz_child_uses_edit_instead_of_insert(tmp_path: Path) -> None:
    parent = tmp_path / "article.tex"
    child = tmp_path / "diagram.tex"
    child.write_text(
        "\\begin{tikzpicture}\n\\node (a) at (1,2) {Hello};\n"
        "\\end{tikzpicture}\n",
        encoding="utf-8",
    )
    source = "Before\n\\input{diagram}\nAfter\n"
    parent.write_text(source, encoding="utf-8")
    manager = TikZDocumentManager(tmp_path)
    reference = manager.find_reference(
        source, parent, source.index("\\input") + 4
    )
    assert reference is not None
    assert reference.source_path == child
    assert reference.tex_reference == "\\input{diagram}"


def test_direct_tikz_source_is_editable(tmp_path: Path) -> None:
    path = tmp_path / "nodes.tex"
    source = "\\begin{tikzpicture}\n\\end{tikzpicture}\n"
    path.write_text(source, encoding="utf-8")
    reference = TikZDocumentManager(tmp_path).find_reference(
        source, path, source.index("tikzpicture") + 2
    )
    assert reference is not None
    assert reference.source_path == path


def test_tikz_presets_and_history_are_source_backed() -> None:
    store = read("Services/TikZ/TikZStylePresetStore.swift")
    router = read("Services/GraphicEditorSessionRouter.swift")
    workspace = read("Views/TikZ/TikZWorkspaceView.swift")
    assert "UserDefaults.standard.set" in store
    assert "func save(" in store and "func delete(" in store
    assert "func undoTikZ()" in router and "func redoTikZ()" in router
    assert 'historyGroup: "node-move:' in workspace
    assert "editingNodeName = created?.name" in workspace
    assert "stylePresets.nodeStyle(for: shape)" in workspace


def test_triangle_is_supported_in_source_and_direct_canvas() -> None:
    parser = read("Services/TikZ/TikZGraphParser.swift")
    writer = read("Services/TikZ/TikZSourceEditor.swift")
    canvas = read("Views/TikZ/TikZCanvasView.swift")
    assert 'options.value(for: "regular polygon sides") == "3"' in parser
    assert 'options.setValue("3", for: "regular polygon sides")' in writer
    assert "TikZTriangleShape()" in canvas


def test_circle_and_ellipse_share_one_icon_only_tool() -> None:
    tools = read("Models/TikZ/TikZCanvasTool.swift")
    model = read("Models/TikZ/TikZGraph.swift")
    workspace = read("Views/TikZ/TikZWorkspaceView.swift")
    assert "case circle" not in tools
    assert "case circle" in model
    strip = read("Views/TikZ/TikZToolStyleStripView.swift")
    assert 'case .ellipse: return "circle"' in strip
    assert "TikZToolStyleStripView.tools" in workspace
    assert 'Label("Styles"' not in workspace
    assert '"Save current style' not in workspace
    assert 'title: "Ellipse"' not in workspace
    assert 'title: "Circle"' not in workspace
    assert "tool: .circle" not in workspace
    canvas = read("Views/TikZ/TikZCanvasView.swift")
    assert "activeTool == .circle" not in canvas
    assert "activeTool == .ellipse" in canvas
    assert "Ellipse()" in canvas


def test_circle_and_ellipse_morph_when_resized_in_display_coordinates() -> None:
    geometry = read("Services/TikZ/TikZRoundShapeGeometry.swift")
    source = read("Services/TikZ/TikZSourceEditor.swift")
    workspace = read("Views/TikZ/TikZWorkspaceView.swift")
    renderer = read("Utilities/TikZ/TikZNodeGeometry.swift")
    store = read("Services/TikZ/TikZStylePresetStore.swift")
    assert "renderedWidth" in geometry and "renderedHeight" in geometry
    assert "circleTolerance" in geometry
    assert "resultingShape == .circle" in source
    assert "resultingShape == .ellipse" in source
    assert "displayCanvasSize: logicalCanvasSize" in workspace
    assert "node.shape == .circle" in renderer
    assert "min(size.width, size.height)" in renderer
    assert "shape == .circle ? TikZNodeShape.ellipse.rawValue" in store


def test_canvas_menu_coordinates_use_visible_viewport() -> None:
    content = read("Views/ContentView.swift")
    palette = read("Views/QuickDrawingToolPaletteView.swift")
    preview = read("Views/PencilContactToolPreviewView.swift")
    assert "GeometryReader { viewport in" in content
    assert "width: viewport.size.width" in content
    assert "let below = anchor.y + pencilGap + halfHeight" in palette
    assert "proxy.size.height - 21" in preview


def test_desktop_preview_has_edit_action() -> None:
    widget = (
        ROOT / "src/nd_mind_mirror/ui/editor/latex/source_tikz_preview_widget.py"
    ).read_text(encoding="utf-8")
    controller = (
        ROOT / "src/nd_mind_mirror/ui/editor/latex/source_preview/tikz/"
        "source_tikz_preview_controller_core.py"
    ).read_text(encoding="utf-8")
    assert 'menu.addAction("Edit TikZ in iPad…")' in widget
    assert "widget.edit_requested.connect(self._open_tikz_preview_in_ipad)" in controller


def test_tikz_event_watcher_accepts_an_external_bridge(tmp_path: Path) -> None:
    import json

    from PySide6.QtCore import QCoreApplication

    from nd_mind_mirror.ui.window.main.tikz_update_event_controller import (
        TikZUpdateEventController,
    )

    app = QCoreApplication.instance() or QCoreApplication([])
    controller = TikZUpdateEventController(tmp_path)
    received: list[str] = []
    controller.updated.connect(received.append)

    event = tmp_path / ".nd_mind_mirror" / "tikz_update_event.json"
    event.parent.mkdir(parents=True)
    event.write_text(
        json.dumps({"path": "example/tikz.tex", "client_revision": 4}),
        encoding="utf-8",
    )
    controller._poll()
    controller._emit_pending()
    controller._poll_timer.stop()
    controller._emit_timer.stop()
    assert received == ["example/tikz.tex"]


def test_auto_layout_uses_actual_dimensions_not_full_width() -> None:
    source = read("Services/TikZ/TikZAutoLayoutService.swift")
    assert "max(node.width" in source and "max(node.height" in source
    assert "totalPrimary / 2" in source
    assert "12 * layerFraction" not in source
