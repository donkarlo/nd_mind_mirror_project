"""Regression checks for desktop-driven TikZ creation/editing and compact iPad UI."""

from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]


def _manager_class():
    path = ROOT / 'src/nd_mind_mirror/graphic/tikz/tikz_document_manager.py'
    spec = importlib.util.spec_from_file_location('tikz_document_manager_test', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.TikZDocumentManager


def test_manager_creates_collision_safe_child_and_resolves_input(tmp_path: Path) -> None:
    manager = _manager_class()(tmp_path)
    parent = tmp_path / 'main.tex'
    parent.write_text('before\nafter\n', encoding='utf-8')
    first = manager.create_for_source(parent)
    second = manager.create_for_source(parent)
    assert first.source_path.name == 'tikz.tex'
    assert second.source_path.name == 'tikz_2.tex'
    assert first.source_path.read_text(encoding='utf-8') == '\\begin{tikzpicture}\n\n\\end{tikzpicture}\n'
    source = f'before\n{first.tex_reference}\nafter\n'
    position = source.index(first.tex_reference) + 2
    found = manager.find_reference(source, parent, position)
    assert found is not None
    assert found.source_path == first.source_path


def test_source_and_visual_contexts_expose_create_edit_tikz() -> None:
    source_mixin = (ROOT / 'src/nd_mind_mirror/ui/editor/bookmark/selection_bookmark_editor_mixin.py').read_text(encoding='utf-8')
    visual = (ROOT / 'src/nd_mind_mirror/ui/editor/bookmark/selection_bookmark_visual_context_controller.py').read_text(encoding='utf-8')
    for text in (source_mixin, visual):
        assert 'Create TikZ in iPad…' in text
        assert 'Edit TikZ in iPad…' in text
    assert '_handle_tikz_context_request' in source_mixin


def test_bridge_waits_for_hello_and_accepts_desktop_open() -> None:
    client = (ROOT / 'src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/TikZ/TikZBridgeClient.swift').read_text(encoding='utf-8')
    server = (ROOT / 'src/nd_mind_mirror/graphic/tikz/bridge/server.py').read_text(encoding='utf-8')
    connect_body = client.split('func connect()', 1)[1].split('func disconnect()', 1)[0]
    assert 'isConnected = true' not in connect_body
    assert 'case "hello"' in client
    assert 'send(["type": "list_files"])' in client
    assert 'case "desktop_open"' in client
    assert 'desktopOpenToken += 1' in client
    assert 'self.app.post("/desktop/open")' in server


def test_workspace_switch_is_compact_and_sidebar_starts_hidden() -> None:
    tabs = (ROOT / 'src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/GraphicWorkspaceTabsView.swift').read_text(encoding='utf-8')
    workspace = (ROOT / 'src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZWorkspaceView.swift').read_text(encoding='utf-8')
    assert '.frame(width: 112)' in tabs
    assert '.padding(.trailing, 62)' in tabs
    assert 'ContentView()' in tabs
    assert 'TikZWorkspaceView(bridge: tikzBridge)' in tabs
    assert '@StateObject private var tikzBridge = TikZBridgeClient()' in tabs
    assert '.onChange(of: tikzBridge.desktopOpenToken)' in tabs
    assert 'NavigationSplitViewVisibility = .detailOnly' in workspace
