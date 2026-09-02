// Serializes iPad graphic saves, coalesces newer states, and retries one in-flight save.

import Foundation
import SwiftUI

/// Keeps one save in flight so each acknowledgement maps to an unambiguous canvas snapshot.
@MainActor
final class GraphicSaveRetryController: ObservableObject {
    @Published private(set) var isAwaitingAcknowledgement = false
    @Published private(set) var didExhaustRetries = false

    private let retryDelayNanoseconds: UInt64
    private let maximumRetryCount: Int
    private var retryCount = 0
    private var retryTask: Task<Void, Never>?
    private var inFlightSendAction: (() -> Bool)?
    private var queuedLatestSendAction: (() -> Bool)?
    private var deferredCloseAction: (() -> Void)?

    init(
        retryDelayNanoseconds: UInt64 = 2_000_000_000,
        maximumRetryCount: Int = 2
    ) {
        self.retryDelayNanoseconds = retryDelayNanoseconds
        self.maximumRetryCount = max(maximumRetryCount, 0)
    }

    /// Sends immediately when idle; while a save is pending, keeps only the newest replacement state.
    func submitSave(_ sendAction: @escaping () -> Bool) {
        didExhaustRetries = false
        if isAwaitingAcknowledgement {
            queuedLatestSendAction = sendAction
            return
        }
        beginSave(sendAction)
    }

    /// Completes the in-flight save, then sends the newest queued state before allowing close.
    func acknowledgeSave() {
        guard isAwaitingAcknowledgement else { return }
        retryTask?.cancel()
        retryTask = nil
        inFlightSendAction = nil
        retryCount = 0

        if let queued = queuedLatestSendAction {
            queuedLatestSendAction = nil
            beginSave(queued)
            return
        }

        isAwaitingAcknowledgement = false
        let closeAction = deferredCloseAction
        deferredCloseAction = nil
        closeAction?()
    }

    /// Runs close immediately when idle, otherwise defers it until all queued saves are acknowledged.
    @discardableResult
    func closeWhenSettled(_ action: @escaping () -> Void) -> Bool {
        guard isAwaitingAcknowledgement else {
            action()
            return false
        }
        deferredCloseAction = action
        return true
    }

    /// Cancels retry, queued-save, and deferred-close state for a new authoritative document.
    func reset() {
        retryTask?.cancel()
        retryTask = nil
        inFlightSendAction = nil
        queuedLatestSendAction = nil
        deferredCloseAction = nil
        retryCount = 0
        isAwaitingAcknowledgement = false
        didExhaustRetries = false
    }

    private func beginSave(_ sendAction: @escaping () -> Bool) {
        retryTask?.cancel()
        inFlightSendAction = sendAction
        retryCount = 0
        isAwaitingAcknowledgement = true
        guard sendAction() else {
            isAwaitingAcknowledgement = false
            inFlightSendAction = nil
            return
        }
        scheduleRetry()
    }

    private func scheduleRetry() {
        retryTask = Task { [weak self] in
            guard let self else { return }
            do {
                try await Task.sleep(nanoseconds: retryDelayNanoseconds)
            } catch {
                return
            }
            guard isAwaitingAcknowledgement, let sendAction = inFlightSendAction else { return }
            guard retryCount < maximumRetryCount else {
                exhaustRetries()
                return
            }

            retryCount += 1
            guard sendAction() else {
                exhaustRetries()
                return
            }
            scheduleRetry()
        }
    }

    private func exhaustRetries() {
        isAwaitingAcknowledgement = false
        didExhaustRetries = true
        retryTask?.cancel()
        retryTask = nil
        inFlightSendAction = nil
        queuedLatestSendAction = nil
        deferredCloseAction = nil
        retryCount = 0
    }
}
