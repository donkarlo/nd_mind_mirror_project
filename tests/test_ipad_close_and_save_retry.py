from pathlib import Path

ROOT = Path(__file__).parent
CONTENT_VIEW = (ROOT.parent / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/ContentView.swift").read_text()
RETRY = (ROOT.parent / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/GraphicSaveRetryController.swift").read_text()
SESSION = (ROOT.parent / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/GraphicBridgeClientDocumentSession.swift").read_text()


def test_close_button_keeps_bridge_session_alive():
    assert 'accessibilityLabel("Close image")' in CONTENT_VIEW
    assert 'closeCurrentDocumentKeepingListener()' in CONTENT_VIEW
    assert 'Text("Waiting for image from Ubuntu")' in CONTENT_VIEW
    assert 'selectedPath = nil' in SESSION
    assert 'documentToken += 1' in SESSION
    assert 'disconnect()' not in SESSION


def test_close_waits_for_all_pending_save_acknowledgements():
    assert 'closeWhenSettled' in CONTENT_VIEW
    assert 'Saving before closing…' in CONTENT_VIEW
    assert 'status.hasPrefix("Saved —")' in CONTENT_VIEW
    assert 'acknowledgeSave()' in CONTENT_VIEW
    assert 'deferredCloseAction' in RETRY
    assert 'if let queued = queuedLatestSendAction' in RETRY


def test_retry_serializes_saves_and_keeps_only_latest_queued_state():
    assert 'retryDelayNanoseconds: UInt64 = 2_000_000_000' in RETRY
    assert 'maximumRetryCount: Int = 2' in RETRY
    assert 'inFlightSendAction' in RETRY
    assert 'queuedLatestSendAction = sendAction' in RETRY
    assert 'guard retryCount < maximumRetryCount else' in RETRY
    assert 'didExhaustRetries = true' in RETRY
    assert 'queuedLatestSendAction = nil' in RETRY


def test_content_view_routes_real_saves_through_serial_controller():
    assert 'saveRetryController.submitSave' in CONTENT_VIEW
    assert 'return bridge.status == "Saving…"' in CONTENT_VIEW
    save_function = CONTENT_VIEW.split('private func save(', 1)[1].split('private func handleBridgeStatus', 1)[0]
    assert save_function.index('saveRetryController.submitSave') < save_function.index('bridge.save(')
