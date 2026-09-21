"""Regression checks for deterministic iPad TikZ selection, Pencil connectors, and arrow dependencies."""

from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_canvas_uses_one_central_interaction_layer() -> None:
    canvas = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZCanvasView.swift"
    )
    node = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZNodeView.swift"
    )
    edge = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZEdgeView.swift"
    )
    assert "TikZCanvasInteractionOverlay(" in canvas
    assert ".highPriorityGesture" not in node
    assert ".simultaneousGesture" not in node
    assert ".contextMenu" not in node
    assert ".highPriorityGesture" not in edge
    assert ".contextMenu" not in edge


def test_pencil_connector_auto_activates_last_connector_from_connection_point() -> None:
    coordinator = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZCanvasInteractionCoordinator.swift"
    )
    workspace = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZWorkspaceView.swift"
    )
    assert "singleTap.require(toFail: doubleTap)" in coordinator
    assert "UITouch.TouchType.pencil.rawValue" in coordinator
    assert "handleConnectorPan" in coordinator
    assert "activeTool.connectorKind != nil || activeTool == .select" in coordinator
    assert "TikZConnectionPointGeometry" in coordinator
    assert "onConnectorAutoActivated?()" in coordinator
    assert "lastConnectorTool" in workspace
    assert "activateLastConnectorTool" in workspace


def test_blank_connector_drop_is_resolved_by_workspace_dialog() -> None:
    coordinator = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZCanvasInteractionCoordinator.swift"
    )
    workspace = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZWorkspaceView.swift"
    )
    assert "onConnectorDragEnded?(sourceName, target?.node.name, point)" in coordinator
    assert ".confirmationDialog(" in workspace
    assert '"Connect to Rectangle"' in workspace
    assert '"Connect to Ellipse"' in workspace
    assert '"Delete Connector"' in workspace


def test_long_press_menu_has_connection_point_and_requested_actions() -> None:
    coordinator = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZCanvasInteractionCoordinator.swift"
    )
    assert "UIContextMenuInteraction" in coordinator
    assert 'title: "Duplicate"' in coordinator
    assert 'title: "Add connection point"' in coordinator
    assert 'title: "Bring to Front"' in coordinator
    assert 'title: "Send to Back"' in coordinator
    assert 'title: "Delete"' in coordinator
    assert "UIKeyCommand" not in coordinator


def test_style_updates_are_explicit_bindings_not_global_onchange() -> None:
    workspace = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZWorkspaceView.swift"
    )
    assert "nodeStyleBinding" in workspace
    assert "edgeStyleBinding" in workspace
    assert ".onChange(of: nodeStyle)" not in workspace
    assert ".onChange(of: edgeStyle)" not in workspace


def test_arrow_and_ellipse_dependencies_are_written_into_tikz_source() -> None:
    dependencies = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/TikZ/TikZSourceDependencyManager.swift"
    )
    editor = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/TikZ/TikZSourceEditor.swift"
    )
    assert '"arrows.meta"' in dependencies
    assert '"shapes.geometric"' in dependencies
    assert "ensuringArrowsMeta" in editor
    assert "ensuringShapesGeometric" in editor
    assert '"-{Latex}"' in editor
    assert '"-{Latex[open]}"' in editor


def test_lualatex_accepts_filled_and_open_latex_arrowheads(tmp_path: Path) -> None:
    lualatex = shutil.which("lualatex")
    if lualatex is None:
        pytest.skip("lualatex is not installed")

    source = textwrap.dedent(
        r"""
        \documentclass{article}
        \usepackage{tikz}
        \begin{document}
        \usetikzlibrary{arrows.meta}
        \usetikzlibrary{shapes.geometric}
        \begin{tikzpicture}
        \node[draw,rectangle] (a) at (0,0) {};
        \node[draw,ellipse] (b) at (2,0) {};
        \draw[-{Latex}] (a) -- (b);
        \draw[dashed,-{Latex[open]}] (a) -- ++(2,-1);
        \end{tikzpicture}
        \end{document}
        """
    ).strip() + "\n"

    tex = tmp_path / "main.tex"
    tex.write_text(source, encoding="utf-8")
    completed = subprocess.run(
        [
            lualatex,
            "-interaction=nonstopmode",
            "-halt-on-error",
            tex.name,
        ],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
