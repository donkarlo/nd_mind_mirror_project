from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reverse_transport_reader_accepts_large_autosave_messages() -> None:
    server = (ROOT / "src/nd_mind_mirror/graphic/bridge/server.py").read_text(encoding="utf-8")
    assert "self.max_tcp_message_bytes = 128 * 1024 * 1024" in server
    assert "limit=self.max_tcp_message_bytes" in server
    assert "asyncio.open_connection(" in server
    assert "self.ipad_listener_port" in server


def test_ipad_keeps_canvas_visible_during_transport_reconnect() -> None:
    content = (
        ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/ContentView.swift"
    ).read_text(encoding="utf-8")
    assert "if bridge.selectedPath != nil" in content
    assert "else if bridge.isConnected" in content
    assert content.index("if bridge.selectedPath != nil") < content.index("else if bridge.isConnected")


def test_ipad_persists_ten_recent_pencil_colors() -> None:
    service = (
        ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/RecentPencilColors.swift"
    ).read_text(encoding="utf-8")
    content = (
        ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/ContentView.swift"
    ).read_text(encoding="utf-8")
    assert 'private let maximumCount = 10' in service
    assert 'UserDefaults.standard.stringArray(forKey: defaultsKey)' in service
    assert 'UserDefaults.standard.set(hexColors, forKey: defaultsKey)' in service
    assert 'recentColorStrip' in content
    assert 'recentColors.remember(pencilUsedForThisDrawing.color)' in content
