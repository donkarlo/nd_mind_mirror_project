"""Regression checks for automatic shared-bridge routing of iPad image/TikZ editing."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_desktop_context_exposes_tikz_without_replacing_image_actions() -> None:
    source = _read(
        "src/nd_mind_mirror/ui/editor/bookmark/selection_bookmark_editor_mixin.py"
    )
    visual = _read(
        "src/nd_mind_mirror/ui/editor/bookmark/selection_bookmark_visual_context_controller.py"
    )
    for text in (source, visual):
        assert "Create TikZ in iPad…" in text
        assert "Edit TikZ in iPad…" in text
        assert "image in iPad…" in text


def test_tikz_notifier_uses_shared_graphic_bridge() -> None:
    notifier = _read("src/nd_mind_mirror/graphic/tikz/tikz_bridge_notifier.py")
    assert 'bridge_http_url: str = "http://127.0.0.1:8766"' in notifier
    assert '"/open-tikz"' in notifier
    assert '"tikz_open_request.json"' in notifier
    assert "8765" not in notifier


def test_bridge_server_routes_image_and_tikz_over_one_reverse_connection() -> None:
    launcher = _read("src/nd_mind_mirror/graphic/bridge/__main__.py")
    server = _read("src/nd_mind_mirror/graphic/bridge/unified_server.py")
    assert "ConfiguredUnifiedGraphicBridgeServer" in launcher
    assert 'message_type == "update_tikz"' in server
    assert 'message_type == "render_tikz"' in server
    assert '"type": "open_tikz"' in server
    assert "self.tcp_clients" in server


def test_bridge_opens_tikz_before_rendering_preview() -> None:
    server = _read("src/nd_mind_mirror/graphic/bridge/unified_server.py")
    open_method_start = server.index("async def _send_tikz_open")
    schedule_start = server.index("def _schedule_tikz_render", open_method_start)
    open_method = server[open_method_start:schedule_start]
    assert '"type": "open_tikz"' in open_method
    assert "await self._send_tcp(" in open_method
    assert "self._schedule_tikz_render(writer, path, source)" in open_method
    assert open_method.index("await self._send_tcp(") < open_method.index(
        "self._schedule_tikz_render(writer, path, source)"
    )


def test_bridge_keeps_latest_durable_tikz_request_pending_until_delivery() -> None:
    server = _read("src/nd_mind_mirror/graphic/bridge/unified_server.py")
    assert "self._last_seen_tikz_open_request_mtime_ns = initial_mtime" in server
    assert "self._last_delivered_tikz_open_request_mtime_ns = 0" in server
    assert "await self._deliver_latest_pending_editor_request(writer)" in server


def test_ipad_has_no_manual_image_tikz_tab_switch_and_keeps_bridge_view_alive() -> None:
    app = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/NDGraphicApp.swift"
    )
    router = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/GraphicWorkspaceRouterView.swift"
    )
    assert "GraphicWorkspaceRouterView()" in app
    assert "ContentView()" in router
    assert "TikZWorkspaceView" in router
    assert "Picker(" not in router
    assert ".opacity(router.workspace == .image ? 1 : 0)" in router
    assert ".allowsHitTesting(router.workspace == .image)" in router


def test_ipad_shared_client_routes_open_messages_by_type() -> None:
    client = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/GraphicBridgeClient.swift"
    )
    session = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/GraphicEditorSessionRouter.swift"
    )
    assert 'case "open_graphic"' in client
    assert 'case "open_tikz"' in client
    assert '"type": "update_tikz"' in session
    assert '"type": "render_tikz"' in session
    assert "attachSender" in client


def test_tikz_workspace_has_no_second_connection_or_file_browser() -> None:
    workspace = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/TikZ/TikZWorkspaceView.swift"
    )
    assert "TikZBridgeClient" not in workspace
    assert "serverURL" not in workspace
    assert "Refresh files" not in workspace
    assert "NavigationSplitView" not in workspace
    assert "@ObservedObject var router: GraphicEditorSessionRouter" in workspace


def test_responsive_bridge_acks_save_before_background_render() -> None:
    server = _read("src/nd_mind_mirror/graphic/bridge/responsive_unified_server.py")
    event_index = server.index("_write_tikz_update_event(relative, revision)")
    ack_index = server.index('"type": "tikz_saved"')
    render_index = server.index("_schedule_tikz_render(", ack_index)
    assert event_index < ack_index < render_index
