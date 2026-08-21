from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bridge_publishes_fast_desktop_event_and_uses_small_ack() -> None:
    server = (ROOT / "src/nd_mind_mirror/graphic/bridge/server.py").read_text(encoding="utf-8")
    assert 'graphic_update_event.json' in server
    assert 'self._write_update_event(sidecar, image_path, revision)' in server
    assert '"type": "graphic_saved"' in server
    assert 'background_image_base64' in server


def test_desktop_has_low_latency_graphic_refresh_path() -> None:
    main = (ROOT / "src/nd_mind_mirror/ui/window/main/main_window.py").read_text(encoding="utf-8")
    assert 'self._graphic_update_event_timer.setInterval(40)' in main
    assert 'def _sync_graphic_update_event' in main
    assert 'self._editor_panel.refresh_current_visual_graphics()' in main
    assert 'self._graphic_preview_refresh_timer.start()' in main
    assert 'self._refresh_current_preview(immediate=False)' in main


def test_navigator_can_edit_managed_graphic_on_ipad() -> None:
    panel = (ROOT / "src/nd_mind_mirror/ui/panel/file_system/file_system_panel.py").read_text(encoding="utf-8")
    main = (ROOT / "src/nd_mind_mirror/ui/window/main/main_window.py").read_text(encoding="utf-8")
    assert 'graphic_edit_requested = Signal(str)' in panel
    assert '"Edit image in iPad…"' in panel
    assert 'self.graphic_edit_requested.emit' in panel
    assert 'def _edit_graphic_from_navigator' in main
    assert 'request_open(sidecar, operation="update")' in main


def test_structure_current_section_is_highlighted_pale_yellow() -> None:
    structure = (
        ROOT / "src/nd_mind_mirror/ui/panel/structure/latex_structure_panel.py"
    ).read_text(encoding="utf-8")
    main = (ROOT / "src/nd_mind_mirror/ui/window/main/main_window.py").read_text(encoding="utf-8")
    assert 'QColor("#fff6bf")' in structure
    assert 'def set_current_line' in structure
    assert 'target.setBackground(0, self._highlight_brush)' in structure
    assert 'self._structure_panel.set_current_line(int(line))' in main


def test_ipad_canvas_supports_pan_pinch_zoom_and_photo_background() -> None:
    package = ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"
    canvas = (package / "Views/PencilCanvasView.swift").read_text(encoding="utf-8")
    content = (package / "Views/ContentView.swift").read_text(encoding="utf-8")
    renderer = (package / "Utilities/GraphicImageRenderer.swift").read_text(encoding="utf-8")
    message = (package / "Models/GraphicMessage.swift").read_text(encoding="utf-8")

    assert 'UIScrollView' in canvas
    assert 'pinchGestureRecognizer' in canvas
    assert 'viewForZooming' in canvas
    assert '.pencilOnly' in canvas
    assert 'PhotosPicker' in content
    assert 'photo.badge.plus' in content
    assert 'backgroundImage: backgroundImage' in content
    assert 'persistBackground: true' in content
    assert 'backgroundImage.draw' in renderer
    assert 'backgroundImageBase64' in message


def test_ipad_autosave_is_quicker_and_ack_does_not_reopen_document() -> None:
    package = ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"
    content = (package / "Views/ContentView.swift").read_text(encoding="utf-8")
    bridge = (package / "Services/GraphicBridgeClient.swift").read_text(encoding="utf-8")
    assert '55_000_000' in content
    assert 'case "graphic_saved":' in bridge
    assert 'applyRemote(message, statusPrefix: "Updated")' in bridge
