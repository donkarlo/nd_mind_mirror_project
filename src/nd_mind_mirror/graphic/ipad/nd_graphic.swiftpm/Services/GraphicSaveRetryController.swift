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
    private let closeMaximumWaitNanoseconds: UInt64
    private var retryCount = 0
    private var retryTask: Task<Void, Never>?
    private var closeDeadlineTask: Task<Void, Never>?
    private var inFlightSendAction: (() -> Bool)?
    private var queuedLatestSendAction: (() -> Bool)?
    private var deferredCloseAction: (() -> Void)?

    init(
        retryDelayNanoseconds: UInt64 = 2_000_000_000,
        maximumRetryCount: Int = 2,
        closeMaximumWaitNanoseconds: UInt64 = 2_000_000_000
    ) {
        self.retryDelayNanoseconds = retryDelayNanoseconds
        self.maximumRetryCount = max(maximumRetryCount, 0)
        self.closeMaximumWaitNanoseconds = closeMaximumWaitNanoseconds
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
        runDeferredClose()
    }

    /// Runs close immediately when idle and otherwise guarantees a bounded wait for save acknowledgement.
    @discardableResult
    func closeWhenSettled(_ action: @escaping () -> Void) -> Bool {
        guard isAwaitingAcknowledgement else {
            action()
            return false
        }
        deferredCloseAction = action

        // closeCurrentImage submits the final canvas state immediately before
        // calling this method. If another save was still awaiting ACK, that
        // final state is the queued action; transmit it now instead of waiting
        // for an acknowledgement that may never arrive.
        if let queued = queuedLatestSendAction {
            queuedLatestSendAction = nil
            retryTask?.cancel()
            retryTask = nil
            inFlightSendAction = queued
            retryCount = 0
            guard queued() else {
                isAwaitingAcknowledgement = false
                inFlightSendAction = nil
                runDeferredClose()
                return false
            }
            scheduleRetry()
        }

        scheduleCloseDeadline()
        return true
    }

    /// Cancels retry, queued-save, close-deadline, and deferred-close state for a new authoritative document.
    func reset() {
        retryTask?.cancel()
        retryTask = nil
        closeDeadlineTask?.cancel()
        closeDeadlineTask = nil
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
            runDeferredClose()
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

    private func scheduleCloseDeadline() {
        guard closeDeadlineTask == nil else { return }
        closeDeadlineTask = Task { [weak self] in
            guard let self else { return }
            do {
                try await Task.sleep(nanoseconds: closeMaximumWaitNanoseconds)
            } catch {
                return
            }
            guard deferredCloseAction != nil else { return }
            didExhaustRetries = true
            cancelPendingSaveState()
            runDeferredClose()
        }
    }

    private func exhaustRetries() {
        isAwaitingAcknowledgement = false
        didExhaustRetries = true
        retryTask?.cancel()
        retryTask = nil
        inFlightSendAction = nil
        queuedLatestSendAction = nil
        retryCount = 0
        runDeferredClose()
    }

    private func cancelPendingSaveState() {
        retryTask?.cancel()
        retryTask = nil
        inFlightSendAction = nil
        queuedLatestSendAction = nil
        retryCount = 0
        isAwaitingAcknowledgement = false
    }

    private func runDeferredClose() {
        closeDeadlineTask?.cancel()
        closeDeadlineTask = nil
        let closeAction = deferredCloseAction
        deferredCloseAction = nil
        closeAction?()
    }
}
