"""Regression checks for the live iPad TikZ round-trip requested on 2026-09-14."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_tikz_toolbar_has_connector_without_help_text_or_trash() -> None:
    workspace = _read("swift/Views/TikZ/TikZWorkspaceView.swift")
    assert 'title: "Connector"' in workspace
    assert 'tool: .connector' in workspace
    assert 'systemName: "trash"' not in workspace
    assert "Pencil drag shape→shape" not in workspace
    assert "Tap to select" not in workspace


def test_connector_pan_runs_only_in_connector_mode() -> None:
    coordinator = _read("swift/Views/TikZ/TikZCanvasInteractionCoordinator.swift")
    assert "guard activeTool == .connector" in coordinator
    assert "connectorPan?.isEnabled = activeTool == .connector" in coordinator
    began = coordinator.split("case .began:", 1)[1].split("case .changed:", 1)[0]
    assert "onNodeSingleTap" not in began


def test_hidden_raster_workspace_stays_alive_but_cannot_intercept_touches() -> None:
    router = _read("swift/Views/GraphicWorkspaceRouterView.swift")
    assert "ContentView()" in router
    assert ".opacity(router.workspace == .image ? 1 : 0)" in router
    assert ".allowsHitTesting(router.workspace == .image)" in router
    assert ".accessibilityHidden(router.workspace != .image)" in router
    assert "TikZWorkspaceView" in router


def test_tikz_save_event_precedes_background_render() -> None:
    server = _read("python/graphic/bridge/responsive_unified_server.py")
    event_index = server.index("self._write_tikz_update_event(relative, revision)")
    ack_index = server.index('"type": "tikz_saved"')
    render_index = server.index("self._schedule_tikz_render(", ack_index)
    assert event_index < ack_index < render_index
    assert '"timestamp_ns": time.time_ns()' in server
    assert '"client_revision": int(client_revision)' in server


def test_source_projects_input_and_include_tikz_below_source_line() -> None:
    controller = _read("python/ui/editor/latex/source_tikz_preview_controller.py")
    assert r"\\(?:input|include)" in controller
    assert "preview_for_input(raw, editor.source_path)" in controller
    assert "setBottomMargin" in controller
    assert "SourceTikZPreviewWidget" in controller


def test_desktop_event_refreshes_source_visual_and_pdf_preview() -> None:
    window = _read("python/ui/window/main/enhanced_main_window.py")
    assert "SourceTikZPreviewController" in window
    assert "TikZUpdateEventController" in window
    assert "notify_tikz_changed(path)" in window
    assert "refresh_current_visual_graphics()" in window
    assert "_refresh_current_preview(immediate=True)" in window


def test_ipad_version_is_03148_build_78() -> None:
    package = _read("swift/Package.swift")
    assert 'displayVersion: "0.31.48"' in package
    assert 'bundleVersion: "78"' in package
