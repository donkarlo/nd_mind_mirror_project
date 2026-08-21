from pathlib import Path


ROOT = Path("src/nd_mind_mirror")


def test_bridge_keeps_websocket_and_legacy_direct_tcp_fallback() -> None:
    server = (ROOT / "graphic/bridge/server.py").read_text(encoding="utf-8")
    main = (ROOT / "graphic/bridge/__main__.py").read_text(encoding="utf-8")
    assert 'self.app.websocket("/ws")' in server
    assert "asyncio.start_server(" in server
    assert "tcp_client_connected" in server
    assert "tcp://{self.tcp_host}:{self.tcp_port}" in server
    assert 'writer.write(data + b"\\n")' in server
    assert 'parser.add_argument("--tcp-port", type=int, default=8767' in main


def test_ipad_reverses_connection_direction_to_bypass_local_network_privacy() -> None:
    package = ROOT / "graphic/ipad/nd_graphic.swiftpm"
    client = (package / "Services/GraphicBridgeClient.swift").read_text(encoding="utf-8")
    content = (package / "Views/ContentView.swift").read_text(encoding="utf-8")
    manifest = (package / "Package.swift").read_text(encoding="utf-8")
    assert "NWListener(" in client
    assert "newConnectionHandler" in client
    assert "listenerPort: UInt16 = 8768" in client
    assert '"type": "ipad_listener"' in client
    assert "Start listening for Ubuntu" in content
    assert ".localNetwork(" not in manifest


def test_bridge_launcher_prints_imported_version_and_reverse_transport() -> None:
    launcher = (ROOT / "graphic/bridge/run_graphic_bridge.sh").read_text(encoding="utf-8")
    assert 'print(f"  version: {bridge.__version__}")' in launcher
    assert 'print(f"  module:  {bridge.__file__}")' in launcher
    assert 'websocket: http://$HOST:$PORT' in launcher
    assert 'reverse iPad transport:' in launcher
