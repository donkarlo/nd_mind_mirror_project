from pathlib import Path


def test_ipad_diagnostics_are_visible_and_persistent() -> None:
    root = Path(__file__).resolve().parents[1]
    package = root / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"
    bridge = (package / "Services/GraphicBridgeClient.swift").read_text(encoding="utf-8")
    content = (package / "Views/ContentView.swift").read_text(encoding="utf-8")

    assert "NWPathMonitor" in bridge
    assert "iPad listener state=" in bridge
    assert "Accepted TCP state=" in bridge
    assert "nd_graphic_diagnostics.log" in bridge
    assert 'Button("Copy log")' in content
    assert 'Button("Run diagnostics")' in content
    assert "ShareLink" in content


def test_bridge_exposes_diagnostic_ping_and_file_log() -> None:
    root = Path(__file__).resolve().parents[1]
    server = (root / "src/nd_mind_mirror/graphic/bridge/server.py").read_text(encoding="utf-8")
    assert 'self.app.get("/diagnostics/ping")' in server
    assert "graphic_bridge.log" in server
    assert "WebSocket attempt from" in server
    assert "Reverse iPad listener discovered" in server
