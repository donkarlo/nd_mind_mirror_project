from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IPAD = ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"


def test_ipad_no_longer_depends_on_local_network_permission_gate():
    client = (IPAD / "Services/GraphicBridgeClient.swift").read_text()
    manifest = (IPAD / "Package.swift").read_text()
    assert "NWListener(" in client
    assert "LocalNetworkPermissionRequester.shared.request" not in client
    assert "openDirectTCP" not in client
    assert ".localNetwork(" not in manifest


def test_ubuntu_discovers_and_connects_to_ipad_listener():
    text = (ROOT / "src/nd_mind_mirror/graphic/bridge/server.py").read_text()
    assert "_reverse_connector_loop" in text
    assert "_discover_ipad_listener" in text
    assert "asyncio.open_connection(" in text
    assert "limit=self.max_tcp_message_bytes" in text
    assert 'greeting.get("type", "")' in text
    assert '"ipad_listener"' in text
    assert "Reverse iPad listener discovered" in text


def test_bridge_still_logs_legacy_direct_tcp_attempts():
    text = (ROOT / "src/nd_mind_mirror/graphic/bridge/server.py").read_text()
    assert "Direct TCP attempt from" in text
    assert "Direct TCP accepted from" in text
