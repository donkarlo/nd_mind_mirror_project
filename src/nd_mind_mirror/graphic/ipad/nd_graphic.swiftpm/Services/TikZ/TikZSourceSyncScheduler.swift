// Rate-limits canonical TikZ source uploads while always keeping the newest edit.

import Foundation

@MainActor
final class TikZSourceSyncScheduler {
    private let interval: TimeInterval
    private var pendingWorkItem: DispatchWorkItem?
    private var latestAction: (() -> Void)?
    private var lastSentUptime = -Double.greatestFiniteMagnitude

    init(updateRateHz: Double = 20.0) {
        interval = 1.0 / max(updateRateHz, 1.0)
    }

    var hasPendingUpdate: Bool {
        latestAction != nil
    }

    func submit(_ action: @escaping () -> Void) {
        latestAction = action

        let now = ProcessInfo.processInfo.systemUptime
        let elapsed = now - lastSentUptime
        if elapsed >= interval {
            sendLatest()
            return
        }

        guard pendingWorkItem == nil else {
            return
        }

        let delay = max(interval - elapsed, 0)
        let workItem = DispatchWorkItem { [weak self] in
            Task { @MainActor in
                self?.sendLatest()
            }
        }
        pendingWorkItem = workItem
        DispatchQueue.main.asyncAfter(
            deadline: .now() + delay,
            execute: workItem
        )
    }

    func flush() {
        pendingWorkItem?.cancel()
        pendingWorkItem = nil
        sendLatest()
    }

    func cancel() {
        pendingWorkItem?.cancel()
        pendingWorkItem = nil
        latestAction = nil
    }

    private func sendLatest() {
        pendingWorkItem?.cancel()
        pendingWorkItem = nil
        guard let action = latestAction else {
            return
        }
        latestAction = nil
        lastSentUptime = ProcessInfo.processInfo.systemUptime
        action()
    }
}
