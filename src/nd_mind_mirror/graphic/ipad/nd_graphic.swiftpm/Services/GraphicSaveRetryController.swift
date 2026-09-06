// Serializes iPad graphic saves, coalesces newer states, and retries until acknowledgement or document close/reset.

import Foundation
import SwiftUI

/// Keeps one save in flight so each acknowledgement maps to an unambiguous canvas snapshot.
@MainActor
final class GraphicSaveRetryController: ObservableObject {
    @Published private(set) var isAwaitingAcknowledgement = false
    @Published private(set) var didExhaustRetries = false

    private let retryDelayNanoseconds: UInt64
    private let closeMaximumWaitNanoseconds: UInt64
    private var retryTask: Task<Void, Never>?
    private var closeDeadlineTask: Task<Void, Never>?
    private var inFlightSendAction: (() -> Bool)?
    private var queuedLatestSendAction: (() -> Bool)?
    private var deferredCloseAction: (() -> Void)?

    init(
        retryDelayNanoseconds: UInt64 = 800_000_000,
        closeMaximumWaitNanoseconds: UInt64 = 2_000_000_000
    ) {
        self.retryDelayNanoseconds = retryDelayNanoseconds
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
        // calling this method. If a newer state is queued, make it the active
        // retry payload now. It remains eligible for retries until ACK or the
        // close deadline, even when the transport is temporarily disconnected.
        if let queued = queuedLatestSendAction {
            queuedLatestSendAction = nil
            retryTask?.cancel()
            retryTask = nil
            inFlightSendAction = queued
            _ = queued()
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
        isAwaitingAcknowledgement = false
        didExhaustRetries = false
    }

    private func beginSave(_ sendAction: @escaping () -> Bool) {
        retryTask?.cancel()
        inFlightSendAction = sendAction
        isAwaitingAcknowledgement = true

        // Do not discard the save when the bridge transport is momentarily
        // unavailable. The same latest state is retried until the bridge ACKs
        // it, or until reset/close explicitly terminates this document session.
        _ = sendAction()
        scheduleRetry()
    }

    private func scheduleRetry() {
        retryTask?.cancel()
        retryTask = Task { [weak self] in
            guard let self else { return }
            do {
                try await Task.sleep(nanoseconds: retryDelayNanoseconds)
            } catch {
                return
            }
            guard isAwaitingAcknowledgement,
                  deferredCloseAction == nil,
                  let sendAction = inFlightSendAction else {
                return
            }

            _ = sendAction()
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

    private func cancelPendingSaveState() {
        retryTask?.cancel()
        retryTask = nil
        inFlightSendAction = nil
        queuedLatestSendAction = nil
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
