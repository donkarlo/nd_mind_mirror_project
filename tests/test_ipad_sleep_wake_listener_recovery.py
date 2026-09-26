"""Regression checks for iPad sleep/wake reverse-listener recovery."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SWIFT_CLIENT = (
    ROOT
    / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/GraphicBridgeClient.swift"
).read_text(encoding="utf-8")


def test_ipad_closes_reverse_transport_only_after_entering_background() -> None:
    assert "UIApplication.didEnterBackgroundNotification" in SWIFT_CLIENT
    assert "UIApplication.willResignActiveNotification" not in SWIFT_CLIENT
    suspension = SWIFT_CLIENT.split(
        "private func prepareForApplicationSuspension()", 1
    )[1].split("private func resumeListeningAfterWake()", 1)[0]
    assert "applicationIsActive = false" in suspension
    assert "applicationWasBackgrounded = true" in suspension
    assert "cancelListenerRecovery()" in suspension
    assert "stopTransport(keepStatus: true)" in suspension
    assert "shouldMaintainListener = false" not in suspension


def test_ipad_rebinds_listener_after_background_wake_with_delay() -> None:
    wake = SWIFT_CLIENT.split(
        "private func resumeListeningAfterWake()", 1
    )[1].split("private func scheduleListenerRecovery(", 1)[0]
    assert "applicationIsActive = true" in wake
    assert "guard applicationWasBackgrounded else { return }" in wake
    assert "applicationWasBackgrounded = false" in wake
    assert 'reason: "application wake"' in wake
    assert "wakeRestartDelayNanoseconds" in wake


def test_listener_waiting_and_failure_states_retry_automatically() -> None:
    assert 'reason: "listener waiting:' in SWIFT_CLIENT
    assert 'reason: "listener failed:' in SWIFT_CLIENT
    assert "failedListenerRetryDelayNanoseconds" in SWIFT_CLIENT


def test_network_path_recovery_can_restart_missing_listener() -> None:
    assert "path.status == .satisfied" in SWIFT_CLIENT
    assert "self.listener == nil" in SWIFT_CLIENT
    assert 'reason: "network path became satisfied"' in SWIFT_CLIENT


def test_reverse_heartbeat_capability_remains_advertised() -> None:
    assert '"capabilities": ["heartbeat_pong"]' in SWIFT_CLIENT
