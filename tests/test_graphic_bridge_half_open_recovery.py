"""Regression checks for application-acknowledged iPad reverse-connection recovery."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVISION = (
    ROOT
    / "src/nd_mind_mirror/graphic/bridge/revision_aware_server.py"
).read_text(encoding="utf-8")
HEALTH = (
    ROOT
    / "src/nd_mind_mirror/graphic/bridge/reverse_tcp_connection_health_policy.py"
).read_text(encoding="utf-8")
SWIFT_CLIENT = (
    ROOT
    / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/GraphicBridgeClient.swift"
).read_text(encoding="utf-8")
SWIFT_MESSAGE = (
    ROOT
    / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Models/GraphicMessage.swift"
).read_text(encoding="utf-8")


def test_reverse_connection_keeps_aggressive_tcp_liveness() -> None:
    assert "SO_KEEPALIVE" in HEALTH
    assert "TCP_KEEPIDLE" in HEALTH
    assert "TCP_KEEPINTVL" in HEALTH
    assert "TCP_KEEPCNT" in HEALTH
    assert "TCP_USER_TIMEOUT" in HEALTH


def test_open_delivery_requires_real_ipad_application_ack() -> None:
    assert 'payload["delivery_id"] = delivery_id' in REVISION
    assert '"open_graphic_ack"' in REVISION
    assert "_accept_open_graphic_ack" in REVISION
    assert "reverse TCP application ACK" in REVISION
    assert "_confirm_delivery_after_health_window" not in REVISION
    assert "survives the keepalive window" not in REVISION


def test_ipad_acknowledges_only_after_applying_open_graphic() -> None:
    open_case = SWIFT_CLIENT.split('case "open_graphic":', 1)[1].split(
        'case "graphic_saved":', 1
    )[0]
    assert "applyRemote(message" in open_case
    assert "acknowledgeOpen(message)" in open_case
    assert open_case.index("applyRemote(message") < open_case.index("acknowledgeOpen(message)")
    assert '"type": "open_graphic_ack"' in SWIFT_CLIENT
    assert '"delivery_id": deliveryID' in SWIFT_CLIENT
    assert "var deliveryID: String?" in SWIFT_MESSAGE
    assert 'case deliveryID = "delivery_id"' in SWIFT_MESSAGE


def test_missing_ack_drops_socket_and_leaves_request_pending_for_reconnect() -> None:
    timeout = REVISION.split(
        "    async def _expire_open_delivery", 1
    )[1].split(
        "    def _accept_open_graphic_ack", 1
    )[0]
    assert "iPad open ACK timeout" in timeout
    assert "self.tcp_clients.discard(writer)" in timeout
    assert "writer.close()" in timeout
    assert "_mark_open_request_delivered" not in timeout


def test_reconnect_resends_unacknowledged_open_request() -> None:
    assert "await self._deliver_pending_open_request(writer)" in REVISION
    assert "Resent pending explicit iPad open request after reconnect; awaiting ACK" in REVISION


def test_duplicate_http_and_watcher_delivery_is_coalesced() -> None:
    broadcast = REVISION.split(
        "    async def _broadcast_open", 1
    )[1].split(
        "    async def _send_open_tcp", 1
    )[0]
    assert "_is_open_delivery_pending" in broadcast
    assert "Coalesced duplicate explicit iPad open while ACK is pending" in broadcast
