from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reverse_transport_uses_incoming_ipad_connection() -> None:
    ipad = ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm"
    client = (ipad / "Services/GraphicBridgeClient.swift").read_text()
    server = (ROOT / "src/nd_mind_mirror/graphic/bridge/server.py").read_text()
    assert "NWListener(using: parameters, on: port)" in client
    assert '"type": "ipad_listener"' in client
    assert "ipad_listener_port: int = 8768" in server
    assert "_candidate_lan_hosts" in server
    assert "ipaddress.ip_network" in server
    assert "asyncio.open_connection(" in server
    assert "limit=self.max_tcp_message_bytes" in server
