"""Regression checks for reconnecting after the iPad is suspended or sleeps."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVISION = (
    ROOT / "src/nd_mind_mirror/graphic/bridge/revision_aware_server.py"
).read_text(encoding="utf-8")
HEARTBEAT = (
    ROOT / "src/nd_mind_mirror/graphic/bridge/reverse_tcp_heartbeat_monitor.py"
).read_text(encoding="utf-8")
SWIFT_CLIENT = (
    ROOT
    / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/GraphicBridgeClient.swift"
).read_text(encoding="utf-8")


def test_reverse_transport_requires_application_level_pong() -> None:
    assert '"heartbeat_ping"' in HEARTBEAT
    assert "_PONG_TIMEOUT_SECONDS" in HEARTBEAT
    assert "self._pong_event.wait()" in HEARTBEAT
    assert "no iPad application heartbeat_pong" in HEARTBEAT
    assert "ReverseTcpHeartbeatMonitor" in REVISION
    assert '"heartbeat_pong"' in REVISION
    assert "monitor.acknowledge()" in REVISION




def test_heartbeat_is_capability_negotiated_for_backward_compatibility() -> None:
    assert '"capabilities": ["heartbeat_pong"]' in SWIFT_CLIENT
    assert 'greeting.get("capabilities", [])' in REVISION
    assert 'if "heartbeat_pong" in capabilities:' in REVISION

def test_heartbeat_timeout_removes_stale_writer_before_rediscovery() -> None:
    timeout = REVISION.split(
        "    async def _drop_stale_reverse_connection", 1
    )[1].split(
        "    async def _handle_tcp", 1
    )[0]
    assert "self.tcp_clients.discard(writer)" in timeout
    assert "writer.close()" in timeout
    assert "dropping stale connection" in timeout


def test_ipad_replies_to_heartbeat_from_application_code() -> None:
    heartbeat_case = SWIFT_CLIENT.split(
        'case "heartbeat_ping":', 1
    )[1].split(
        'case "open_graphic":', 1
    )[0]
    assert 'send(["type": "heartbeat_pong"])' in heartbeat_case


def test_ipad_rebuilds_listener_only_after_real_background_wake() -> None:
    assert "UIApplication.didEnterBackgroundNotification" in SWIFT_CLIENT
    assert "UIApplication.willResignActiveNotification" not in SWIFT_CLIENT
    assert "UIApplication.didBecomeActiveNotification" in SWIFT_CLIENT

    suspension = SWIFT_CLIENT.split(
        "    private func prepareForApplicationSuspension()", 1
    )[1].split(
        "    private func resumeListeningAfterWake()", 1
    )[0]
    assert "applicationWasBackgrounded = true" in suspension
    assert "stopTransport(keepStatus: true)" in suspension

    resume = SWIFT_CLIENT.split(
        "    private func resumeListeningAfterWake()", 1
    )[1].split(
        "    private func scheduleListenerRecovery(", 1
    )[0]
    assert "guard applicationWasBackgrounded else { return }" in resume
    assert "guard shouldMaintainListener else { return }" in resume
    assert 'reason: "application wake"' in resume


def test_manual_disconnect_disables_automatic_resume() -> None:
    public_disconnect = SWIFT_CLIENT.split(
        "    func disconnect()", 1
    )[1].split(
        "    private func stopTransport(", 1
    )[0]
    assert "shouldMaintainListener = false" in public_disconnect
    assert "applicationWasBackgrounded = false" in public_disconnect
