"""Static checks for TikZ selection deletion, long-press actions, and connector styles."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_delete_is_long_press_only_not_toolbar() -> None:
    workspace = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZWorkspaceView.swift"
    )
    assert 'systemName: "trash"' not in workspace
    assert "deleteSelected" not in workspace


def test_long_press_menu_is_owned_by_central_interaction_controller() -> None:
    coordinator = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZCanvasInteractionCoordinator.swift"
    )
    assert "UIContextMenuInteraction" in coordinator
    assert 'title: "Edit label"' in coordinator
    assert 'title: "Duplicate"' in coordinator
    assert 'title: "Add connection point"' in coordinator
    assert 'title: "Bring to Front"' in coordinator
    assert 'title: "Send to Back"' in coordinator
    assert 'title: "Delete"' in coordinator


def test_connector_style_supports_solid_dashed_and_open_filled_heads() -> None:
    style = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Models/TikZ/TikZEdgeStyle.swift"
    )
    toolbar = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZStyleToolbarView.swift"
    )
    source = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/TikZ/TikZSourceEditor.swift"
    )
    assert "TikZLinePattern" in style
    assert "TikZArrowHeadStyle" in style
    assert "linePatternPicker" in toolbar
    assert "arrowHeadPicker" in toolbar
    assert 'setFlag("dashed"' in source
    assert '"-{Latex}"' in source
    assert '"-{Latex[open]}"' in source


def test_deleting_node_also_removes_connected_simple_edges() -> None:
    source = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/TikZ/TikZSourceEditor.swift"
    )
    assert "static func deleteNode" in source
    assert "$0.source == name" in source
    assert "$0.target == name" in source
    assert "deleteEdge(" in source


def test_pencil_connector_can_start_implicitly_with_last_connector_tool() -> None:
    workspace = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZWorkspaceView.swift"
    )
    coordinator = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZCanvasInteractionCoordinator.swift"
    )
    assert 'tool: .straightConnector' in workspace
    assert 'tool: .curveConnector' in workspace
    assert 'tool: .polylineConnector' in workspace
    assert "lastConnectorTool" in workspace
    assert "activeTool.connectorKind != nil || activeTool == .select" in coordinator
    assert "onConnectorAutoActivated?()" in coordinator
    assert "UITouch.TouchType.pencil.rawValue" in coordinator
